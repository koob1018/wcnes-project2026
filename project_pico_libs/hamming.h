/*
  Hamming code library for backscatter project in WCNES at Uppsala University
  Authors: Albin Kjellson, Oskar Svanström, Samson Kahsay Tesfalem
*/
#ifndef HAMMING_H
#define HAMMING_H

#include <stdint.h>
#include <inttypes.h>

/*
    Encode a payload using hamming code
    byte array: The original payload
    payload_length: The length of the original payload (in bits)
    total_bits: Hamming code total bits (e.g. 7 for Hamming(7,4))
    data_bits: Hamming code data bits (e.g. 4 for Hamming(7,4))
    returns: new payload with parity bits
*/
uint8_t* encode(uint8_t *byte_array, uint8_t payload_length, uint8_t total_bits, uint8_t data_bits);

#endif