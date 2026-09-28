# -*- coding: utf-8 -*-
"""工银智译 · 一键运行入口

用法：
    python run.py

前置：
    1) pip install -r requirements.txt
    2) cp .env.example engine/.env  并填入你的 DEEPSEEK_API_KEY
    3) 把产品资料 PDF 放入 data/（支持子文件夹，文件名随意）

本脚本依次执行：引擎全链路（链一~链六 + 保真度探针）→ 生成可点原型 HTML。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

ENV_PATH = os.path.join(HERE, 'engine', '.env')


def preflight():
    ok = True
    if not os.environ.get('DEEPSEEK_API_KEY') and not os.path.exists(ENV_PATH):
        print('[前置检查] 未找到 DEEPSEEK_API_KEY：请执行  cp .env.example engine/.env  并填入 key')
        ok = False
    missing = []
    for mod in ('langchain_core', 'langchain_deepseek', 'langgraph', 'pypdf', 'pydantic'):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print('[前置检查] 缺少依赖：%s → 请执行  pip install -r requirements.txt' % '、'.join(missing))
        ok = False
    if not os.path.isdir(os.path.join(HERE, 'data')):
        print('[前置检查] 未找到 data/ 目录')
        ok = False
    return ok


def step(title, script, cwd):
    print('\n' + '#' * 74)
    print('# %s' % title)
    print('#' * 74)
    r = subprocess.run([PY, os.path.join(HERE, script)], cwd=cwd)
    if r.returncode != 0:
        print('\n!! 步骤失败（退出码 %d）：%s' % (r.returncode, script))
        sys.exit(r.returncode)


def main():
    if not preflight():
        sys.exit(1)
    step('引擎全链路（链一~链六 + 保真度探针）', os.path.join('engine', 'run_all.py'),
         os.path.join(HERE, 'engine'))
    step('生成可点交互原型', os.path.join('ui', 'build_prototype.py'),
         os.path.join(HERE, 'ui'))
    print('\n全部完成。用浏览器打开 ui/prototype.html 即可演示。')


if __name__ == '__main__':
    main()
