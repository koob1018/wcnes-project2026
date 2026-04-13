# Metric Formulas

This file records the formulas used by `plot_position_metrics.py` for the `position*.txt` logs.

## 1. Packet Error Rate (PER)

Let `seq_i` be the sequence number of the `i`-th received packet in chronological order.

The number of missing packets between two adjacent received packets is estimated as:

$$m_i = (seq_i - seq_{i-1} - 1) \bmod 256$$

The total estimated number of missing packets is:

$$M = \sum_{i=2}^{N} m_i$$

The estimated total transmitted packets inside the captured window is:

$$T = N + M$$

Then the Packet Error Rate is:

$$PER = \frac{M}{T}$$

## 2. Bit Error Rate (BER)

The notebook-compatible BER calculation compares the received payload against the expected payload generated from the pseudo sequence number.

For one packet:

$$BER = \frac{\text{number of wrong bits}}{\text{total number of received bits}}$$

For a file:

$$BER_{file} = \frac{\sum \text{wrong bits across packets}}{\sum \text{total received bits across packets}}$$

## 3. RSSI

RSSI is summarized as the arithmetic mean of the valid packets in one log file:

$$RSSI_{avg} = \frac{1}{N} \sum_{i=1}^{N} RSSI_i$$

## Notes

- CRC is ignored in this analysis.
- The PER above is an estimate derived from sequence-number gaps in the received log.
- The figures use tag position on the X axis and show PER, BER, and RSSI in three shared-X subplots.
