using System;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading;
using Microsoft.Xna.Framework;
using MonoMod.Cil;
using Terraria;

namespace TerraBridge;

public sealed partial class TerraBridge
{
    private bool backgroundHookInstalled;
    private bool backgroundInputHookInstalled;
    private long profileRefreshDeadline;
    private string runtimeSnapshot = "{\"protocol\":1,\"status\":\"not_sampled\"}";

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);

    private static bool? NativeWindowFocus()
    {
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows)) return null;
        IntPtr window = GetForegroundWindow();
        if (window == IntPtr.Zero || GetWindowThreadProcessId(window, out uint pid) == 0) return null;
        return pid == (uint)Environment.ProcessId;
    }

    private bool EffectiveFocus(bool engineFocused)
    {
        // FNA can retain IsActive=true after Windows focus has moved elsewhere.
        // Normalize only verified training gameplay; preserve vanilla behavior elsewhere.
        if (trainingAllowed && !Main.gameMenu && Main.netMode == 0)
            return NativeWindowFocus() ?? engineFocused;
        return engineFocused;
    }

    private void InstallBackgroundHook()
    {
        IL_Main.DoUpdate += PatchFocusPause;
        IL_Player.Update += PatchBackgroundInput;
        On_Main.DoUpdate += UpdateRuntime;
    }

    private void RemoveBackgroundHook()
    {
        On_Main.DoUpdate -= UpdateRuntime;
        IL_Main.DoUpdate -= PatchFocusPause;
        IL_Player.Update -= PatchBackgroundInput;
        backgroundHookInstalled = false;
        backgroundInputHookInstalled = false;
    }

    private void PatchFocusPause(ILContext il)
    {
        backgroundHookInstalled = false;
        // Only alter the single focus-pause branch. Keep the real hasFocus field,
        // input focus, UI pauses and multiplayer behavior unchanged.
        var matches = il.Body.Instructions.Where(i => i.MatchLdsfld<Main>("hasFocus") &&
            i.Next != null && (i.Next.OpCode == Mono.Cecil.Cil.OpCodes.Brtrue ||
                              i.Next.OpCode == Mono.Cecil.Cil.OpCodes.Brtrue_S)).ToArray();
        if (matches.Length != 1) {
            Logger.Warn("Background mode unsupported: expected one focus-pause branch.");
            return;
        }
        var cursor = new ILCursor(il);
        cursor.Goto(matches[0], MoveType.After);
        cursor.EmitDelegate<Func<bool, bool>>(focused => EffectiveFocus(focused) || AllowBackground());
        backgroundHookInstalled = true;
    }

    private void PatchBackgroundInput(ILContext il)
    {
        backgroundInputHookInstalled = false;
        var matches = il.Body.Instructions.Where(i => i.MatchLdsfld<Main>("hasFocus") &&
            i.Previous != null && i.Previous.MatchCall<Player>("ResetControls")).ToArray();
        if (matches.Length != 1) {
            Logger.Warn("Background input unsupported: expected one post-ResetControls focus branch.");
            return;
        }
        var cursor = new ILCursor(il);
        cursor.Goto(matches[0], MoveType.Before);
        cursor.Emit(Mono.Cecil.Cil.OpCodes.Ldarg_0);
        cursor.EmitDelegate<Action<Player>>(p => {
            // Vanilla skips ModPlayer.SetControls when hasFocus=false. Apply only
            // bridge input here; keep physical input skipped and never double-count.
            if (!Main.hasFocus && AllowBackground() && p.whoAmI == Main.myPlayer)
                ApplyControls(p);
        });
        backgroundInputHookInstalled = true;
    }

    private bool AllowBackground() => backgroundHookInstalled && backgroundInputHookInstalled && backgroundRequested &&
        trainingAllowed && !Main.gameMenu && Main.netMode == 0;

    private void UpdateRuntime(On_Main.orig_DoUpdate orig, Main self, ref GameTime gameTime)
    {
        // This hook still runs when normal world updates return early for focus
        // or manual pause. All game reads and marker checks stay on this thread.
        long now = Stopwatch.GetTimestamp();
        if (now >= profileRefreshDeadline) {
            RefreshTrainingProfile();
            profileRefreshDeadline = now + Stopwatch.Frequency;
        }
        orig(self, ref gameTime);
        string json = JsonSerializer.Serialize(new {
            protocol = 1, status = "ok", instanceId, worldSession,
            sampledAtUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            focused = self.IsActive, paused = Main.gamePaused, menu = Main.gameMenu,
            osFocused = NativeWindowFocus(),
            autoPause = Main.autoPause, backgroundHookInstalled, backgroundInputHookInstalled,
            backgroundEnabled = AllowBackground(),
            checkpointAvailable = checkpoint != null,
            currentPositionBlocker = Main.gameMenu ? null : RestoreBlocker(Main.LocalPlayer, Main.LocalPlayer.position),
            checkpointBlocker = Main.gameMenu || checkpoint == null ? null : RestoreBlocker(Main.LocalPlayer, checkpoint.Position)
        });
        Interlocked.Exchange(ref runtimeSnapshot, json);
    }
}
