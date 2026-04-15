# 参数配置地图（勿修改 — 仅供定位）

本文档只列出有哪些参数、在哪里找到，不涉及修改。

## 一、总体原则
- Tag 侧：直接改 3 个主参数（d0, d1, baud）→ 系统自动推导其他参数
- Receiver 侧：自动匹配 Tag 的推导值，无需手动改
- 编译后烧录到硬件，看 receiver 日志输出验证效果

---

## 二、主要可改参数（在 carrier-receiver-baseband/main.c）

### 2.1 Tag 侧 — 三个关键旋钮

| 参数名 | 定义行 | 当前值 | 单位 | 含义 |
|--------|--------|--------|------|------|
| CLOCK_DIV0 | L40 | 20 | - | d0：符号 0 对应的时钟分频（偶数） |
| CLOCK_DIV1 | L41 | 18 | - | d1：符号 1 对应的时钟分频（偶数） |
| DESIRED_BAUD | L42 | 100000 | bit/s | 符号率（波特率） |

**关键公式**
- f0 = 125 MHz / d0
- f1 = 125 MHz / d1
- center_offset = (f0 + f1) / 2
- deviation = \|f1 - f0\| / 2
- minRxBw ≈ baud + 2 × deviation

### 2.2 Tag 侧 — 其他定义  

| 参数名 | 定义行 | 当前值 | 单位 | 含义 |
|--------|--------|--------|------|------|
| TX_DURATION | L36 | 250 | ms | 向 receiver 发包的间隔 |
| TWOANTENNAS | L43 | true | - | 用双天线或单天线（L6/L27） |
| PIN_TX1 | L44 | 6 | - | Pico GPIO（天线1） |
| PIN_TX2 | L45 | 27 | - | Pico GPIO（天线2） |
| CARRIER_FEQ | L47 | 2450000000 | Hz | 载波频率 |
| RECEIVER | L38 | 1352 | - | receiver 板型（2500 or 1352） |

### 2.3 Payload 侧（在 project_pico_libs/packet_generation.h）

| 参数名 | 定义行 | 当前值 | 单位 | 含义 |
|--------|--------|--------|------|------|
| PAYLOADSIZE | L17 | 14 | byte | 消息有效载荷长度 |
| HEADER_LEN | L18 | 10 | byte | 数据包头部长度（8+1+1） |

---

## 三、推导参数（自动计算，不要直接改）

在 `backscatter_program_init()` 调用时自动推导：

| 参数名 | 自动计算位置 | 被调用处 | 含义 |
|--------|------------|---------|------|
| config->center_offset | backscatter.c L154 | main.c L98 | 中心频率偏移 |
| config->deviation | backscatter.c L155 | main.c L99 | 频偏 |
| config->baudrate | backscatter.c L153 | main.c L100 | 实际波特率（可能修正） |
| config->minRxBw | backscatter.c L156 | main.c L101 | 最小接收带宽 |

Receiver 会自动匹配这些值：
```c
// main.c L98-L101，自动执行
set_frecuency_rx(CARRIER_FEQ + backscatter_conf.center_offset);
set_frequency_deviation_rx(backscatter_conf.deviation);
set_datarate_rx(backscatter_conf.baudrate);
set_filter_bandwidth_rx(backscatter_conf.minRxBw);
```

---

## 四、文件层级关系

```
carrier-receiver-baseband/
├── main.c                           ← 改参数的唯一地点（L36-L47）
└── CMakeLists.txt

project_pico_libs/
├── backscatter.h / backscatter.c    ← 推导center_offset/deviation/minRxBw
├── receiver_CC2500.h / .c           ← receiver端设置函数（自动调用）
├── packet_generation.h              ← PAYLOADSIZE/HEADER_LEN 定义（L17-L18）
└── carrier_CC2500.h / .c            ← carrier端配置
```

**注意：不改 project_pico_libs 的任何东西，都是库层逻辑。**

---

## 五、扫参策略建议（配合本地实验）

### A. 改 d0/d1（影响频偏和中心偏移）
- d0 越小 → f0 越大
- d1 越小 → f1 越大
- d1 - d0 越大 → deviation 越大

### B. 改 baud（影响符号率和时序）
- baud 越大 → 符号越快 → 时序约束更紧
- 接收芯片可实现性受限（CC1352 / CC2500 都有上限）

### C. 改 TX_DURATION（影响发包节奏）
- 不改调制本身，只改节奏
- 用于验证 receiver 接收稳定性

### D. 改 PAYLOADSIZE（测试不同包长）
- 改了会影响 packet_generation.c 里的计算
- 可以测试包长对 PER 的影响

---

## 六. 你回家的扫参思路

### 第 1 步：固定 baud，扫 d0/d1
- 保持 baud = 100000
- 尝试 d0 在 18-24 之间，d1 在 16-22 之间
- 打印输出 center_offset 和 deviation，记录
- 看 receiver 输出 PER/BER

### 第 2 步：固定某个 (d0, d1) 对，扫 baud
- 当 PER 开始改善时，固定分频
- 调 baud，看是否还能优化（50k → 150k 范围）

### 第 3 步（可选）：改 PAYLOADSIZE
- 小步改 PAYLOADSIZE 看对 PER 的影响

---

## 七. 编译和烧录

```bash
# 在 carrier-receiver-baseband 目录
mkdir -p build
cd build
cmake ..
make
# 生成 .uf2 文件后烧录到 Pico
```

修改 main.c 后，就重新编译一次。

---

## 八. Receiver 端验证路经

改完参数、烧录后：
1. Pico 启动，串口会打印 "Computed baseband settings"（自动计算的参数）
2. Receiver（CC1352）会看到这些设置
3. Receiver 上位机记录包接收情况 → stats 脚本计算 PER/BER
4. 对比 baseline 看是否更好

---

## 九. 现场检查清单（回家实验前）

- [ ] 确认 carrier-receiver-baseband/main.c 存在
- [ ] 确认你的编辑器可以快速打开和改 L40-L47
- [ ] 确认能编译和烧录工程
- [ ] 确认 receiver 端软件能采集日志
- [ ] 确认 stats 脚本能算 PER/BER

---

## 十. 明天去 lab 前的交接

把你回家记录的"最优参数组合"和对应的"PER/BER 结果"带上，然后在 lab 用频谱分析仪验证（按 spectrum_measurement_playbook.md）。
