#!/usr/bin/env bash
# Scaffold: a minimal Unity project nested in a git repo, one commit, plus an uncommitted change
# that allocates in Update (a closure and a List per frame).
set -euo pipefail
git init -q -b main .
git config user.name "eval"
git config user.email "eval@example.invalid"
root=Client/Game
mkdir -p "$root/Assets/Scripts" "$root/ProjectSettings" "$root/Packages"
printf 'm_EditorVersion: 6000.3.13f1\n' > "$root/ProjectSettings/ProjectVersion.txt"
printf '{\n  "dependencies": {\n    "com.unity.render-pipelines.universal": "17.0.3"\n  }\n}\n' \
  > "$root/Packages/manifest.json"
cat > "$root/Assets/Scripts/EnemySpawner.cs" <<'CS'
using UnityEngine;

public class EnemySpawner : MonoBehaviour
{
    [SerializeField] private GameObject enemyPrefab;
    [SerializeField] private float interval = 2f;
    private float timer;

    private void Update()
    {
        timer += Time.deltaTime;
        if (timer < interval) return;
        timer = 0f;
        Instantiate(enemyPrefab, transform.position, Quaternion.identity);
    }
}
CS
git add -A
git commit -q -m "Enemy spawner"

cat > "$root/Assets/Scripts/EnemySpawner.cs" <<'CS'
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class EnemySpawner : MonoBehaviour
{
    [SerializeField] private GameObject enemyPrefab;
    [SerializeField] private float interval = 2f;
    private float timer;

    private void Update()
    {
        var alive = new List<GameObject>(GameObject.FindGameObjectsWithTag("Enemy"));
        var near = alive.Where(e => Vector3.Distance(e.transform.position, transform.position) < 10f).ToList();
        timer += Time.deltaTime;
        if (timer < interval || near.Count > 20) return;
        timer = 0f;
        Instantiate(enemyPrefab, transform.position, Quaternion.identity);
    }
}
CS
