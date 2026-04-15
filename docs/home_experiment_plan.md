# deviation 扫描计划（固定 baud=100k，CC1352 receiver）

目标：找到最优的 deviation 值，对应最好的 PER/BER。

## 参数说明
- 固定：`DESIRED_BAUD = 100000`（波特率 100 kbps）
- 变量：`CLOCK_DIV0` 和 `CLOCK_DIV1`
- 约束：两个都必须是偶数；deviation ≤ 1 MHz（CC1352 能力）

## 计算公式（每次改参后可自验）
```
f0 = 125 MHz / d0
f1 = 125 MHz / d1
deviation = |f1 - f0| / 2
center_offset = (f0 + f1) / 2
minRxBw = 100 kHz + 2 × deviation
```

---

## 推荐扫描表（从保守到激进）

按 deviation 从小到大排序，共 7 个测点：

| 测点 | d0 | d1 | f0 (MHz) | f1 (MHz) | deviation (kHz) | center_offset (MHz) | minRxBw (kHz) | 备注 |
|------|----|----|----------|----------|-----------------|-------------------|----------------|------|
| 1 | 24 | 22 | 5.21 | 5.68 | 235 | 5.45 | 570 | 保守，抗干扰强 |
| 2 | 22 | 20 | 5.68 | 6.25 | 285 | 5.97 | 670 | 较保守 |
| 3 | 20 | 18 | 6.25 | 6.94 | 347 | 6.60 | **794** | **当前基线** |
| 4 | 20 | 16 | 6.25 | 7.81 | 780 | 7.03 | 1660 | 激进 |
| 5 | 18 | 16 | 6.94 | 7.81 | 435 | 7.38 | 970 | 中等 |
| 6 | 18 | 14 | 6.94 | 8.93 | 1007 | 7.93 | **3014** | ⚠️ 略超 1 MHz |
| 7 | 22 | 18 | 5.68 | 6.94 | 630 | 6.31 | 1360 | 中-高 |

---

## 摆放配置（固定不变）

本次在家实验采用如下摆放：

```
Carrier ----[0.5m]---- Tag ----[2.5m]---- Receiver
(nRF52840)            (Pico)            (CC1352)
```

**具体参数：**
- Carrier - Tag 距离：0.5 m
- Tag - Receiver 距离：2.5 m
- 总长：3 m（远距离配置）
- 天线朝向：三端一致朝向（需固定）
- 天线高度：离桌面 10-20 cm（垫砖或支架）
- 环境：固定室内位置，不移动

**注意事项：**
- 这是较远的距离（相比推荐 0.5-1m），receiver 接收功率会较弱
- 每次改参后**不要移动设备**，保证位置不变才能对比参数效果
- 明天去 lab 时也要尽量复现这个配置（或调整为 lab 的对标配置）

---

## 在家快速测试计划（建议顺序）

### 第 1 轮：跑 baseline + 两个对比点（15 分钟）
1. **Test 3** (d0=20, d1=18)：当前baseline，记录 PER/BER/RSSI
2. **Test 2** (d0=22, d1=20)：降低 deviation → 看是否抗干扰更好
3. **Test 4** (d0=20, d1=16)：增大 deviation → 看是否 SNR 更好

→ 快速判定趋势

### 第 2 轮（可选）：深入扫描（30 分钟）
如果第 1 轮看到某个方向更优，再密集扫描：
- 如果是"deviation 越小越好"：加测 Test 1
- 如果是"deviation 越大越好"：加测 Test 5 和 Test 7
- 如果 Test 3 最好：保持不变

### 第 3 轮：确认最优点（可选）
- 选出 PER 最好的参数组合
- 跑 5-10 轮重复测试，看稳定性

---

## 现场操作流程（每次改参）

### 步骤 A：修改代码（1 分钟）
打开 `carrier-receiver-baseband/main.c`：
```c
#define CLOCK_DIV0              20  // 改这个
#define CLOCK_DIV1              18  // 改这个
#define DESIRED_BAUD        100000  // 不改
```

对应上面表格的参数改即可（比如改成 d0=22, d1=20）。

### 步骤 B：编译和烧录（3-5 分钟）

**快速一行命令（推荐）**
```bash
cd /Users/yiwenxu/Projects/coursework/wcnes-project2026/carrier-receiver-baseband && \
rm -rf build && mkdir -p build && cd build && cmake .. && make && cd .. && bash flash.sh
```

或者分步执行：
```bash
cd /Users/yiwenxu/Projects/coursework/wcnes-project2026/carrier-receiver-baseband
rm -rf build
mkdir -p build
cd build
cmake ..
make
cd ..
bash flash.sh
```

### 步骤 C：记录结果（2-3 分钟）
等 receiver 开始采集（通常 30 秒内得到第一批包），记录：
- 串口打印的 "Computed baseband settings"（验证 center_offset、deviation、minRxBw）
- PER / BER / RSSI（从 receiver 日志提取）
- 是否有明显差异（好 / 一样 / 变差）

---

## 记录表（直接填）

```
日期：
Baseline (Test 3, d0=20, d1=18)：
- 预期 deviation：347 kHz
- 实测 PER：___ %
- 实测 BER：___
- 实测 RSSI：___ dBm
- 是否稳定：是 / 否

Test ____ (d0=___, d1=___)：
- 预期 deviation：___ kHz
- 实测 PER：___ %
- 实测 BER：___
- 实测 RSSI：___ dBm
- 对比 baseline：优 / 一样 / 差

... (重复)
```

---

## 常见现象解读

| 现象 | 可能原因 | 下一步 |
|------|---------|--------|
| receiver 收不到包 | deviation 太大，超过 receiver 滤波能力或 center_offset 偏离太远 | 回退到更保守的参数 |
| PER 高但没规律 | 环境干扰或天线位置不稳定 | 固定位置、做多次重复测试 |
| deviation 特别大时 PER 更好 | 该环境干扰不严重，SNR 提升主导 | 试更大 deviation（Test 5/6） |
| 所有参数 PER 都一样 | 当前测试条件下性能已饱和或限制在其他地方 | 改 baud 或 PAYLOADSIZE |

---

## 明天去 lab 的交接

选出"PER 最好"的参数组合，记下：
- d0 / d1 的值
- 对应的 deviation 和 center_offset
- 相比 baseline 的 PER 改善百分比

然后用频谱仪按 `spectrum_measurement_playbook.md` 验证这组参数是否真的产生了预期的频谱特性。
