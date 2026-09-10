using System;
using System.Diagnostics;
using System.Text.Json;
using Microsoft.Xna.Framework;
using Terraria;

namespace TerraBridge;

public sealed partial class TerraBridge
{
    private sealed class Operation
    {
        public long Id, Deadline;
        public string Kind, Action;
        public int Frames, Applied;
        public bool Ready;
    }
    private sealed class Checkpoint
    {
        public Vector2 Position;
        public int Life, Mana, Direction;
    }
    private Operation operation;
    private Checkpoint checkpoint;
    private long operationSequence, completedId;
    private string completedResult;
    private static string Error(string message) => JsonSerializer.Serialize(new { protocol = 1, error = message });

    private static string RestoreBlocker(Player p, Vector2 position)
    {
        if (p.mount.Active) return "player_mounted";
        if (p.grapCount > 0) return "player_grappling";
        if (Collision.SolidCollision(position, p.width, p.height)) return "location_solid_collision";
        return null;
    }

    private void CancelOperation(string reason)
    {
        if (operation == null) return;
        completedId = operation.Id;
        completedResult = JsonSerializer.Serialize(new {
            protocol = 1, status = reason, operationId = operation.Id, executedFrames = operation.Applied
        });
        operation = null;
    }
    private void ExpireOperation()
    {
        if (operation != null && Stopwatch.GetTimestamp() > operation.Deadline)
            CancelOperation("timeout");
    }
    private string HandleTraining(string command)
    {
        string[] parts = command.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0) return null;
        if (parts[0] != "step" && parts[0] != "checkpoint" && parts[0] != "reset" && parts[0] != "result") return null;
        lock (actionLock) {
            ExpireOperation();
            if (parts[0] == "result") {
                if (parts.Length != 2 || !long.TryParse(parts[1], out long id)) return Error("Use result ID");
                if (operation?.Id == id) return JsonSerializer.Serialize(new { protocol = 1, status = "pending", operationId = id });
                return completedId == id && completedResult != null ? completedResult : Error("Unknown or superseded operation");
            }
            int frames = 0;
            string a = "idle";
            if (parts[0] == "step") {
                if (parts.Length != 3 || !int.TryParse(parts[2], out frames) || frames < 1 || frames > 120)
                    return Error("Use step ACTION FRAMES (1..120)");
                a = parts[1];
                if (!(a == "idle" || a == "left" || a == "right" || a == "jump" || a == "left_jump" || a == "right_jump"))
                    return Error("Unknown action");
            } else if (parts.Length != 1) return Error("Command takes no arguments");
            if (!worldReady) return Error("Enter a single-player world first");
            if (parts[0] != "step" && !trainingAllowed) return Error("training_profile_required");
            if (operation != null) return Error("Operation in progress");
            if (parts[0] == "reset" && checkpoint == null) return Error("Record checkpoint first");
            action = "stop";
            deadline = 0;
            operation = new Operation {
                Id = ++operationSequence, Kind = parts[0], Action = a, Frames = frames,
                Deadline = Stopwatch.GetTimestamp() + 5 * Stopwatch.Frequency
            };
            return JsonSerializer.Serialize(new { protocol = 1, status = "accepted", operationId = operation.Id });
        }
    }

    // Called at the end of the game update, before constructing the observation.
    internal void PrepareObservation(Player p)
    {
        lock (actionLock) {
            ExpireOperation();
            if (operation == null) return;
            if (operation.Kind == "checkpoint") checkpoint = null;
            if (p.dead) { CancelOperation("player_unavailable"); return; }
            if (operation.Kind != "step") {
                RefreshTrainingProfile();
                if (!trainingAllowed) { CancelOperation("training_profile_required"); return; }
            }
            if (operation.Kind == "checkpoint") {
                // Failed replacement must not leave an older checkpoint usable.
                string blocker = RestoreBlocker(p, p.position);
                if (blocker != null) { CancelOperation("checkpoint_" + blocker); return; }
                if (p.velocity != Vector2.Zero) {
                    CancelOperation("checkpoint_player_moving"); return;
                }
                checkpoint = new Checkpoint { Position = p.position, Life = p.statLife, Mana = p.statMana, Direction = p.direction };
                operation.Ready = true;
            } else if (operation.Kind == "reset") {
                if (checkpoint == null) { CancelOperation("checkpoint_unavailable"); return; }
                string blocker = RestoreBlocker(p, checkpoint.Position);
                if (blocker != null) { CancelOperation("reset_" + blocker); return; }
                p.Teleport(checkpoint.Position);
                p.velocity = Vector2.Zero;
                p.statLife = Math.Min(checkpoint.Life, p.statLifeMax2);
                p.statMana = Math.Min(checkpoint.Mana, p.statManaMax2);
                p.direction = checkpoint.Direction;
                p.fallStart = (int)(p.position.Y / 16);
                p.jump = 0;
                p.releaseJump = true;
                p.controlLeft = p.controlRight = p.controlJump = false;
                operation.Ready = true;
            } else operation.Ready = operation.Applied >= operation.Frames;
        }
    }
    private void CompleteOperation(string observation)
    {
        lock (actionLock) {
            if (operation == null || !operation.Ready) return;
            using JsonDocument doc = JsonDocument.Parse(observation);
            completedId = operation.Id;
            completedResult = JsonSerializer.Serialize(new {
                protocol = 1, status = "completed", operationId = operation.Id,
                kind = operation.Kind, executedFrames = operation.Applied, observation = doc.RootElement
            });
            operation = null;
        }
    }
}
