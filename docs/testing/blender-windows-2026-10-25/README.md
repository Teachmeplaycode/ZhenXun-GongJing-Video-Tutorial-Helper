# Windows Blender 4.5 integration test — 2026-10-25

> **中文摘要**：在 Windows 的 Blender 4.5.0 上，用独立的后台 Blender 实例真实联调「帧寻 Bridge」插件和后端接口（没有 mock）。
> 应用节点成功，首次对答案 10/10 全对；故意删掉变换几何体、剪断组输入→切换.真、把循环最大值改成 5，三处错误全部检出；恢复后再查全对。
> 发现的问题：重复「应用」会新增修改器，而对答案读的是第一个修改器，于是一直报旧树的错。**已在 PR #95 修复**（见文末）。
> 没有验证：图形界面安装、侧栏、浏览器按钮和画布红色描边。

Both checkouts: e7ccd25. Remote project: D:\pyprj\2026\MyTargetProject.
Executable: D:\Blenderrrrrrrrrr\blender.exe (4.5.0).

Used a separate `--background --factory-startup` Blender process. Registered the actual add-on in that process on loopback port 19877, forwarded via SSH to the Mac. FastAPI TestClient exercised the real backend routes with a temporary job and the existing recipe-zone.json fixture. No bridge responses were mocked. Because background Blender does not run its normal GUI event loop, the harness explicitly pumped the add-on's `_tick()` queue. The user's existing Blender process and scene were not changed; no persistent add-on installation was performed.

## Results

- Status: connected, Blender 4.5.0, Cube.
- Add-on download route: byte-for-byte match with the local source.
- Apply: success; initial check: 10/10 nodes, no findings.
- Delete Transform, remove Group Input → Switch.True, set Wrap max to 5: all three mistakes detected.
- Known dangling/contradictory-link issue reproduced: an additional Join Geometry → Simulation Output missing-link finding appears.
- Restore the original tree's node, socket values and connections: 10/10 nodes, no findings.
- Local focused backend regression suite: 5 passed.

## Additional defect reproduced

Applying again creates another geometry-nodes modifier. The bridge's `_tree()` returns the first geometry-nodes modifier, so the subsequent check still reports the damaged old tree, even though the new tree contains all 10 nodes. `results.json` includes both check results and the modifier inventory. This also affects objects that already have another geometry-nodes modifier before applying.

Relevant implementation: `backend/modules/recipe_script.py` always creates a new modifier; `backend/modules/blender/zhenxun_bridge.py::_tree` returns the first matching modifier. A future fix should explicitly associate the requested recipe tree with the applied modifier without overwriting unrelated user data.

## Limits

No graphical installation, sidebar rendering, browser-button interaction, canvas red outlines, or normal GUI timer lifecycle was validated. This is an actual Windows Blender binary/socket/backend-route test, not a desktop UI acceptance test. The local port 8000 service was not reachable during inspection; the backend routes were exercised in-process instead. No full 993/97 regression rerun. No application source changes.

The supplied harness files document the run and contain environment-specific paths. Run test_windows.py from backend with its Python environment while bridge_host.py is running in the isolated remote Blender process and the SSH port forward is active. Output goes to /tmp/zhenxun-win-test, which must exist.

## Fix (PR #95)

- 帧寻 now names what it builds `帧寻·<tree name>` (`recipe_script.owned_name`): applying again reuses that
  modifier and swaps its node group (a material is rebuilt in place and made active), so nothing piles up and
  the person's own modifiers and materials are left alone.
- `export_tree` takes `owned` and reads that modifier/material first, then the last `帧寻·` modifier, then
  the old fallback; the backend's 对答案 passes it.
- Re-checked with Blender 5.0 (bpy): an object with the person's own geometry-nodes modifier, applied,
  Transform deleted, applied again → one `帧寻·几何节点.007` modifier next to theirs, 对答案 reads the new
  tree: all matched. Windows 4.5 not re-run yet.
- Still open: the answer's own contradictory Join Geometry → Simulation Output link can show as missing
  when the node next to it is deleted.
