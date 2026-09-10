using System;
using System.Diagnostics;
using System.Linq;
using System.Text.Json;
using System.Threading;
using Microsoft.Xna.Framework;
using MonoMod.Cil;
using Terraria;

namespace TerraBridge;

public sealed partial class TerraBridge
{
    private bool backgroundHookInstalled;
    private long profileRefreshDeadline;
    private string runtimeSnapshot = "{\"protocol\":1,\"status\":\"not_sampled\"}";

    private void InstallBackgroundHook()
    {
        IL_Main.DoUpdate += PatchFocusPause;
        On_Main.DoUpdate += UpdateRuntime;
    }

    private void RemoveBackgroundHook()
    {
        On_Main.DoUpdate -= UpdateRuntime;
        IL_Main.DoUpdate -= PatchFocusPause;
        backgroundHookInstalled = false;
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
        cursor.EmitDelegate<Func<bool, bool>>(focused => focused || AllowBackground());
        backgroundHookInstalled = true;
    }

    private bool AllowBackground() => backgroundHookInstalled && backgroundRequested &&
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
            autoPause = Main.autoPause, backgroundHookInstalled,
            backgroundEnabled = AllowBackground(),
            checkpointAvailable = checkpoint != null,
            currentPositionBlocker = Main.gameMenu ? null : RestoreBlocker(Main.LocalPlayer, Main.LocalPlayer.position),
            checkpointBlocker = Main.gameMenu || checkpoint == null ? null : RestoreBlocker(Main.LocalPlayer, checkpoint.Position)
        });
        Interlocked.Exchange(ref runtimeSnapshot, json);
    }
}
