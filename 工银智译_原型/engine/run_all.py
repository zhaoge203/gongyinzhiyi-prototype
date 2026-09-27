# -*- coding: utf-8 -*-
"""一键跑通全部链条，保证各 JSON 产物之间一致（避免用旧文件评估新结果）"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

STEPS = [
    ('链一 文档解析', 'chain1_parse.py'),
    ('链二 要素抽取+交叉校验', 'chain2_extract.py'),
    ('链三 分层解读生成', 'chain3_interpret.py'),
    ('链四/五 对照+评测', 'chain4_compare.py'),
    ('链六 状态机(含人工复核演示)', 'chain6_graph.py'),
    ('链五 保真度探针', 'probe_fidelity2.py'),
]

for name, script in STEPS:
    print('\n' + '#' * 82)
    print('# %s  (%s)' % (name, script))
    print('#' * 82)
    r = subprocess.run([PY, os.path.join(HERE, script)], cwd=HERE)
    if r.returncode != 0:
        print('!! %s 失败，退出码 %d' % (script, r.returncode))
        sys.exit(r.returncode)

print('\n全部链条执行完成。')
