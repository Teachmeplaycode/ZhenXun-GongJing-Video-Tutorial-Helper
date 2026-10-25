import asyncio, json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
os.environ['BLENDER_BRIDGE_PORT'] = '19877'
from fastapi.testclient import TestClient
from modules import blender, recipe
from tests.test_replay import job_for
import app
out = Path('/tmp/zhenxun-win-test')
zone = json.loads(Path('../front/e2e/fixtures/recipe-zone.json').read_text())
client = TestClient(app.app)
results = {}
def call(name, method, path, **kw):
    response = getattr(client, method)(path, **kw)
    results[name] = {'http': response.status_code, 'body': response.json()}
    (out / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(name, json.dumps(results[name], ensure_ascii=False), flush=True)
    assert response.status_code == 200, results[name]
    return response.json()
with tempfile.TemporaryDirectory(prefix='zhenxun-win-') as folder:
    job = job_for(Path(folder))
    app.jobs['job1'] = job
    recipe.save(job.root, zone)
    assert call('status','get','/api/blender/status')['connected']
    assert client.get('/api/blender/addon').content == blender.ADDON.read_bytes()
    asyncio.run(blender.call('run_script', code="import bpy\nfor m in list(bpy.context.object.modifiers): bpy.context.object.modifiers.remove(m)"))
    assert call('apply','post','/api/link-jobs/job1/recipe/apply',json={})['ok']
    assert call('correct','post','/api/link-jobs/job1/recipe/check',json={})['done']
    exported = asyncio.run(blender.call('export_tree', target='geometry'))
    (out / 'full.json').write_text(json.dumps(exported, ensure_ascii=False, indent=2))
    code = '''import bpy
obj = bpy.context.object
tree = next(m.node_group for m in obj.modifiers if m.type == 'NODES')
transform = next(n for n in tree.nodes if n.bl_idname == 'GeometryNodeTransform')
tree.nodes.remove(transform)
link = next(l for l in tree.links if l.from_node.bl_idname == 'NodeGroupInput' and l.to_node.bl_idname == 'GeometryNodeSwitch' and l.to_socket.name == 'True')
tree.links.remove(link)
wrap = next(n for n in tree.nodes if n.bl_idname == 'ShaderNodeMath' and n.operation == 'WRAP')
wrap.inputs[1].default_value = 5
'''
    asyncio.run(blender.call('run_script', code=code))
    broken = call('broken','post','/api/link-jobs/job1/recipe/check',json={})
    assert not broken['done']
    texts = [f['text'] for f in broken['findings']]
    assert '少了节点「变换几何体」：Shift+A 搜「变换几何体」添加' in texts
    assert '缺一根线：组输入.几何数据 → 切换.真' in texts
    assert '「循环」的「最大值」应为 3，你的是 5' in texts
    call('repair','post','/api/link-jobs/job1/recipe/apply',json={})
    assert not call('reapplied_still_old','post','/api/link-jobs/job1/recipe/check',json={})['done']
    info = asyncio.run(blender.call('run_script', code="import bpy\nprint([(m.name, m.node_group.name, len(m.node_group.nodes)) for m in bpy.context.object.modifiers if m.type == 'NODES'])"))
    results['modifier_diagnosis'] = info
    repair_code = "import bpy, json\ntree = next(m.node_group for m in bpy.context.object.modifiers if m.type == 'NODES')\nfull = json.loads(" + repr(json.dumps(exported)) + ")\n"
    repair_code += """original = next(n for n in full['nodes'] if n['bl_idname'] == 'GeometryNodeTransform')
node = tree.nodes.new('GeometryNodeTransform')
node.name = original['name']
node.location = original['location']
for socket in original['inputs']:
    if 'value' in socket and socket['value'] is not None:
        node.inputs[socket['name']].default_value = socket['value']
for l in full['links']:
    a, b = tree.nodes[l['from']], tree.nodes[l['to']]
    if not any(x.from_node == a and x.to_node == b and x.from_socket.name == l['out'] and x.to_socket.name == l['in'] for x in tree.links):
        tree.links.new(a.outputs[l['out']], b.inputs[l['in']])
next(n for n in tree.nodes if n.bl_idname == 'ShaderNodeMath' and n.operation == 'WRAP').inputs[1].default_value = 3
"""
    asyncio.run(blender.call('run_script', code=repair_code))
    assert call('manually_repaired','post','/api/link-jobs/job1/recipe/check',json={})['done']
    print('PASS: Windows Blender real socket + backend endpoints + fault injection + repair', flush=True)
