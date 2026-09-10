using System;
using System.IO;
using System.Text.Json;
using Terraria;

namespace TerraBridge;

public sealed partial class TerraBridge
{
    private bool trainingAllowed;
    private string profileId, trainingReason = "not_checked";
    private string worldSession = Guid.NewGuid().ToString("N");
    private readonly string instanceId = Guid.NewGuid().ToString("N");
    internal string WorldSession { get { lock (actionLock) return worldSession; } }

    private static bool LocalFileIn(string path, string directory)
    {
        if (string.IsNullOrEmpty(path) || !File.Exists(path)) return false;
        string full = Path.GetFullPath(path);
        if (!string.Equals(Path.GetDirectoryName(full), Path.GetFullPath(directory), StringComparison.OrdinalIgnoreCase))
            return false;
        // Reject junctions/symlinks redirecting a training path to ordinary saves.
        for (string current = full; current != null; current = Path.GetDirectoryName(current))
            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) return false;
        return true;
    }

    // Game thread only. A marker does not authorize cloud/outside saves.
    internal void RefreshTrainingProfile()
    {
        bool allowed = false;
        string id = null, reason = "training_profile_required";
        try {
            string root = Path.GetFullPath(Main.SavePath);
            string marker = Path.Combine(root, "terramaster-training.json");
            if (File.Exists(marker)) {
                using JsonDocument doc = JsonDocument.Parse(File.ReadAllText(marker));
                var data = doc.RootElement;
                if (data.GetProperty("schema").GetInt32() == 1 &&
                    data.GetProperty("purpose").GetString() == "training" &&
                    string.Equals(Path.GetFullPath(data.GetProperty("saveRoot").GetString()), root, StringComparison.OrdinalIgnoreCase) &&
                    Guid.TryParse(data.GetProperty("profileId").GetString(), out Guid parsed)) {
                    id = parsed.ToString("D");
                    var playerFile = Main.ActivePlayerFileData;
                    var worldFile = Main.ActiveWorldFileData;
                    allowed = Main.netMode == 0 && playerFile != null && worldFile != null &&
                        !playerFile.IsCloudSave && !worldFile.IsCloudSave &&
                        Main.LocalPlayer.name.StartsWith("TM-Training-", StringComparison.Ordinal) &&
                        Main.worldName.StartsWith("TM-Training-", StringComparison.Ordinal) &&
                        LocalFileIn(playerFile.Path, Path.Combine(root, "Players")) &&
                        LocalFileIn(worldFile.Path, Path.Combine(root, "Worlds"));
                    reason = allowed ? "verified_local_training_saves" : "local_training_player_and_world_required";
                }
            }
        }
        catch (Exception ex) when (ex is IOException || ex is UnauthorizedAccessException ||
            ex is JsonException || ex is ArgumentException || ex is FormatException || ex is InvalidOperationException || ex is System.Collections.Generic.KeyNotFoundException) {
            reason = "invalid_training_profile";
        }
        lock (actionLock) {
            trainingAllowed = allowed;
            profileId = id;
            trainingReason = reason;
            if (!allowed) checkpoint = null;
        }
    }

    internal object TrainingState()
    {
        lock (actionLock) return new { allowed = trainingAllowed, profileId, reason = trainingReason };
    }
}
