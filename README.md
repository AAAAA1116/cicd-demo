# CI/CD 演示项目

一个能在本机跑起来的最小 CI/CD 样例：Python 业务代码 + pytest 测试 + GitHub Actions workflow + 本地流水线模拟器。

## 一、先讲清楚三个词

| 词 | 是什么 | 类比 |
| --- | --- | --- |
| **CI/CD** | 理念 / 目标：持续集成、持续交付（部署） | "要保证每次改代码都经过验证再上线" |
| **Pipeline（流水线）** | 理念落地的**流程**：一步一步做什么 | 这份"要保证"的具体操作规程 |
| **Workflow** | 流水线写成机器能执行的**配置文件** | 规程的电子版（`.github/workflows/*.yml`） |

所以是的，**CI/CD 一定是有流程的**。理念回答"要做什么"，流程回答"按什么顺序做"，workflow 是流程的代码化。

## 二、没有 CI/CD 时，人们怎么做（手工流程）

```
改代码 → 本地随手试一下 → 手动打包 → 登服务器 → 覆盖文件 → 祈祷别出事
                    ↑
        这步全靠人肉，忘了测、测漏了、环境不一致，都是事故来源
```

**持续**两个字就是解药：把上面这些动作变成每次提交都自动跑一遍，且**不通过就卡住**。

## 三、有 CI/CD 后的流程

```
git push
   │
   ├─ CI 阶段（每次提交都跑，秒级~分钟级反馈）
   │    1. checkout    拉取代码
   │    2. install     装依赖（带缓存）
   │    3. lint        静态检查（ruff / mypy）
   │    4. test        跑测试  ← 核心闸门，红就停
   │
   └─ CD 阶段（CI 绿了之后，打标签或合入主干才触发）
        5. build       构建产物（zip / docker image / 前端静态文件）
        6. deploy      部署上线（scp / kubectl / 云函数）
```

关键机制：**fail fast**。第 4 步一红，第 5、6 步根本不会执行，坏代码物理上到不了生产环境。

## 四、本项目结构

```
cicd-demo/
├── src/pricing.py              业务代码：订单折扣计算
├── tests/test_pricing.py       15 个测试用例（含档位边界、封顶、异常入参）
├── pytest.ini                  测试配置（pythonpath = src）
├── requirements.txt
├── VERSION                     版本号，CD 用它给产物命名
├── pipeline.py                 ★ 本地流水线模拟器
├── .github/workflows/
│   ├── ci.yml                  CI：push/PR 触发，Python 3.11/3.12/3.13 矩阵跑测试
│   └── cd.yml                  CD：打 tag（v*）触发，构建 + 发布
├── dist/                       build 产物（构建生成）
└── deploy/                     "线上环境"（部署生成）+ DEPLOY_LOG.md 部署记录
```

## 五、本地把整条流水线跑一遍

```powershell
cd cicd-demo

python pipeline.py              # 完整流水线（CI + CD），应该全绿
python pipeline.py --ci-only    # 只跑 CI，不做构建部署
python pipeline.py --inject-bug # 注入一个 bug，看 CI 如何在第 4 步拦下它
```

`--inject-bug` 会临时把 `src/pricing.py` 里 5% 的折扣错改成 50%，跑完自动还原。你会看到：

```
  [ OK ] 3. lint       静态检查      ← 语法没问题，lint 放行
  [FAIL] 4. test       运行测试      ← 6 个用例挂了
  流水线已中止 —— 后续阶段没有执行。
```

注意 **lint 过了但 test 挂了**：语法正确不代表逻辑正确，所以测试这道闸门不能省。

也可以用真实的 pytest 单独跑：

```powershell
python -m pytest -v
```

## 六、推到 GitHub 上用真的 Actions

```bash
git init && git add . && git commit -m "feat: pricing"
git remote add origin <你的仓库>
git push -u origin main          # 触发 ci.yml

git tag v1.0.0 && git push origin v1.0.0   # 触发 cd.yml
```

推完在仓库的 **Actions** 标签页就能看到每次运行的流水线，每个 step 的日志都可点开，概念和本地 `pipeline.py` 的输出一一对应。

## 七、真实项目里还会多出来的东西

- **矩阵测试**：多 Python / Node / OS 版本组合（本项目 `ci.yml` 已演示）
- **覆盖率门槛**：`pytest --cov --cov-fail-under=80`，覆盖率不够就红
- **制品缓存**：`actions/cache` 缓存 pip / npm / 构建缓存，省几分钟
- **密钥管理**：生产密钥放 `Settings → Secrets`，绝不写进 yaml
- **环境分层**：dev → staging → prod，prod 通常需要人工审批（manual approval）
- **部署策略**：蓝绿、金丝雀、回滚脚本

这些都是在"4 步流水线"这个骨架上加挂件，骨架本身不变。
