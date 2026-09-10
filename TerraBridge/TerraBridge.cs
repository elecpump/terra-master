using System;
using System.IO;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using Terraria;
using Terraria.ModLoader;

namespace TerraBridge;

public sealed partial class TerraBridge : Mod
{
    internal static TerraBridge Instance;
    private TcpListener listener;
    private Thread worker;
    private volatile bool stopping;
    private string snapshot = "{\"protocol\":1,\"status\":\"menu\"}";
    private readonly object actionLock = new object();
    private string action = "stop";
    private long deadline, actionId, appliedId, appliedFrames;
    private bool worldReady, wasControlling;

    internal void ResetControl(bool ready)
    {
        lock (actionLock) {
            CancelOperation("world_changed");
            checkpoint = null;
            trainingAllowed = false;
            profileId = null;
            trainingReason = "world_changed";
            worldSession = Guid.NewGuid().ToString("N");
            worldReady = ready;
            action = "stop";
            deadline = 0;
            wasControlling = false;
        }
    }

    private string Handle(string command)
    {
        if (command == "ping") return JsonSerializer.Serialize(new {
            protocol = 1, status = "ok", bridge = "TerraBridge", version = "0.4",
            instanceId, processId = Environment.ProcessId, timeMode = "realtime", observationSchema = 2
        });
        if (command == "observe") return Volatile.Read(ref snapshot);
        string training = HandleTraining(command);
        if (training != null) return training;
        string[] parts = command.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (command == "stop") parts = new[] { "act", "stop", "1" };
        if (parts.Length != 3 || parts[0] != "act" ||
            !(parts[1] == "left" || parts[1] == "right" || parts[1] == "jump" ||
              parts[1] == "left_jump" || parts[1] == "right_jump" || parts[1] == "stop") ||
            !int.TryParse(parts[2], out int ms) || ms < 1 || ms > 1000)
            return "{\"protocol\":1,\"error\":\"Use ping, observe, stop, or act ACTION MS (1..1000)\"}";
        lock (actionLock) {
            ExpireOperation();
            if (parts[1] == "stop") CancelOperation("cancelled");
            else if (operation != null) return Error("Operation in progress");
            if (!worldReady && parts[1] != "stop")
                return "{\"protocol\":1,\"error\":\"Enter a single-player world first\"}";
            action = parts[1];
            deadline = Stopwatch.GetTimestamp() + (long)(ms / 1000.0 * Stopwatch.Frequency);
            actionId++;
            appliedFrames = 0;
            return JsonSerializer.Serialize(new { protocol = 1, status = "accepted", actionId, action, durationMs = ms });
        }
    }

    internal void ApplyControls(Player p)
    {
        lock (actionLock) {
            ExpireOperation();
            if (operation != null && operation.Kind == "step") {
                if (p.dead || Main.netMode != 0) { CancelOperation("player_unavailable"); }
                else {
                    string a = operation.Action;
                    p.controlLeft = a == "left" || a == "left_jump";
                    p.controlRight = a == "right" || a == "right_jump";
                    p.controlJump = a == "jump" || a.EndsWith("_jump");
                    operation.Applied++;
                    wasControlling = true;
                    return;
                }
            }
            bool active = worldReady && Main.netMode == 0 && !Main.gameMenu && !p.dead &&
                action != "stop" && Stopwatch.GetTimestamp() < deadline;
            if (active || wasControlling) {
                p.controlLeft = active && (action == "left" || action == "left_jump");
                p.controlRight = active && (action == "right" || action == "right_jump");
                p.controlJump = active && (action == "jump" || action.EndsWith("_jump"));
            }
            if (active) { appliedId = actionId; appliedFrames++; }
            if (!active) action = "stop";
            wasControlling = active;
        }
    }

    internal object ControlState()
    {
        lock (actionLock) return new {
            actionId, appliedId, appliedFrames, action,
            active = action != "stop" && Stopwatch.GetTimestamp() < deadline
        };
    }

    public override void Load()
    {
        if (Main.dedServ) return;
        Instance = this;
        stopping = false;
        try {
            listener = new TcpListener(IPAddress.Loopback, 17655);
            listener.Start(4);
            worker = new Thread(Serve) { IsBackground = true, Name = "TerraBridge" };
            worker.Start();
            Logger.Info("TerraBridge listening on 127.0.0.1:17655 (protocol 1)");
        }
        catch (SocketException ex) {
            listener?.Stop();
            Logger.Error("TerraBridge could not open port 17655: " + ex.Message);
        }
    }

    internal void Publish(object value)
    {
        string json = JsonSerializer.Serialize(value);
        Interlocked.Exchange(ref snapshot, json);
        CompleteOperation(json);
    }

    private void Serve()
    {
        while (!stopping) {
            try {
                using TcpClient client = listener.AcceptTcpClient();
                client.ReceiveTimeout = 1500;
                client.SendTimeout = 1500;
                using NetworkStream stream = client.GetStream();
                // One bounded ASCII command per connection. Never touch game objects here.
                var command = new StringBuilder();
                while (command.Length < 64) {
                    int b = stream.ReadByte();
                    if (b < 0 || b == '\n') break;
                    if (b != '\r') command.Append((char)b);
                }
                string response = Handle(command.ToString());
                byte[] bytes = Encoding.UTF8.GetBytes(response + "\n");
                stream.Write(bytes, 0, bytes.Length);
            }
            catch (IOException) { }
            catch (SocketException) { if (stopping) break; }
            catch (ObjectDisposedException) { break; }
        }
    }

    public override void Unload()
    {
        stopping = true;
        ResetControl(false);
        listener?.Stop();
        worker?.Join(2000);
        Instance = null;
    }
}

public sealed class ObservationSystem : ModSystem
{
    private long tick;
    public override void OnWorldLoad()
    {
        tick = 0;
        TerraBridge.Instance?.ResetControl(Main.netMode == 0);
    }
    public override void OnWorldUnload()
    {
        TerraBridge.Instance?.ResetControl(false);
        TerraBridge.Instance?.Publish(new { protocol = 1, status = "menu" });
    }

    public override void PostUpdateEverything()
    {
        if (Main.dedServ || Main.gameMenu || TerraBridge.Instance == null) return;
        ++tick;
        Player p = Main.LocalPlayer;
        if (tick == 1 || tick % 60 == 0) TerraBridge.Instance.RefreshTrainingProfile();
        TerraBridge.Instance.PrepareObservation(p);
        // Copy values on the game thread; the network worker only reads immutable JSON.
        TerraBridge.Instance.Publish(new {
            protocol = 1, status = "in_world", tick,
            sampledAtUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            control = TerraBridge.Instance.ControlState(),
            training = TerraBridge.Instance.TrainingState(),
            worldSession = TerraBridge.Instance.WorldSession,
            world = new { id = Main.worldID, widthTiles = Main.maxTilesX, heightTiles = Main.maxTilesY },
            player = new {
                x = p.position.X, y = p.position.Y,
                velocityX = p.velocity.X, velocityY = p.velocity.Y,
                life = p.statLife, maxLife = p.statLifeMax2,
                mana = p.statMana, dead = p.dead, direction = p.direction
            }
        });
    }
}

public sealed class ControlPlayer : ModPlayer
{
    public override void SetControls()
    {
        if (Player.whoAmI == Main.myPlayer) TerraBridge.Instance?.ApplyControls(Player);
    }
}
