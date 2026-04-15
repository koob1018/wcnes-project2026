# 频谱仪测量操作清单（实验现场版）

本文档是实验现场唯一操作入口。每次测量按本文执行，避免口径漂移。

## 1. 目标与最小输出
每次实验只产出两类结论：
- 调制是否按预期实现（center offset / deviation / OBW）
- 自干扰是否下降（目标边带相对载波、on/off 对比）

## 2. 测量前固定项（每次都一样）
- 天线位置、距离、朝向固定
- 设备发射功率配置固定
- 频谱仪输入链路固定（线缆/耦合器/衰减器）
- 仪器参数固定：RBW、VBW、Detector、Ref Level、Input Attenuation

注意：只有在“同一套仪器参数”下，不同实验结果才可比较。

## 3. 两个观察窗口（必须分开）

### 窗口 A：调制质量窗口（用于解释 PER/BER）
- Center: 目标边带中心（本项目默认约 2456 MHz，按实测 f0/f1 更新）
- Span: 2-4 MHz
- Trace: Max Hold
- 测量项：
  1. Marker M1 = f0（左边带峰）
  2. Marker M2 = f1（右边带峰）
  3. OBW = 99%

计算：
- center_offset = (f0 + f1) / 2
- deviation = |f1 - f0| / 2

理论核对：
- 观察 OBW 与 (baud + 2 x deviation) 是否同量级、趋势一致。

### 窗口 B：自干扰窗口（用于看 carrier 压制关系）
- Center: 2450 MHz
- Span: 15-25 MHz（确保同时看到 carrier 与目标边带）
- Trace: Max Hold
- 测量项：
  1. Marker C = carrier 峰值功率 P_carrier
  2. Marker S = 目标边带峰值功率 P_sideband
  3. 计算 Delta_dBc = P_sideband - P_carrier

附加对比（强烈建议）：
- Tag off（不调制）测一次目标边带频点功率 P_off
- Tag on（调制）再测一次目标边带频点功率 P_on
- 计算 DeltaP_onoff = P_on - P_off

解释：
- Delta_dBc 越大（越不负）通常越有利。
- DeltaP_onoff 明显大于 0，说明目标边带是由调制有效抬升，不是噪声偶然波动。

## 4. 现场 6 步法（每次照做）
1. 先设窗口 A，打开 Max Hold，稳定 5-10 秒。
2. 读 M1/M2，记录 f0/f1。
3. 打开 OBW 99%，记录 OBW99。
4. 切到窗口 B，读 P_carrier 与 P_sideband。
5. 做 Tag off / Tag on 两次读数，记录 P_off 与 P_on。
6. 计算 center_offset、deviation、Delta_dBc、DeltaP_onoff。

## 5. 判定规则（最小可用）
若同时满足以下 3 条，可作为“效果变好有物理依据”的证据：
1. center_offset / deviation 更接近目标配置。
2. OBW99 与 (baud + 2 x deviation) 关系一致，且无异常扩展。
3. Delta_dBc 改善或更稳定，且 DeltaP_onoff > 0 且可重复。

## 6. 记录模板（直接填）
- 日期时间：
- 实验编号：
- 固件/commit：
- d0 / d1 / baud：
- 窗口 A：
  - f0 =
  - f1 =
  - OBW99 =
  - center_offset =
  - deviation =
- 窗口 B：
  - P_carrier =
  - P_sideband =
  - Delta_dBc =
  - P_off =
  - P_on =
  - DeltaP_onoff =
- PER / BER / RSSI：
- 结论（优于 baseline 吗）：

## 7. 常见误区（避免）
- 把 2450 MHz 强载波与目标边带一起做 OBW，导致 OBW 失真。
- 换了 RBW/VBW/衰减后直接与旧结果对比。
- 只看绝对功率，不做 Tag off / on 对比。
- 一次改多个参数后试图归因。
