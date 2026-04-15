#include <math.h>
#include "hamming.h"

//byte_array = [0011 1100, 
//                1101 0011]
//byte_array = [0011 1100, 1101 0011]

// Payload = 14B -> 112bits 
// Closest: Hamming(127, 120) 7 parity
// 112/4*3  Hamming(7, 4)     84 parity
uint8_t* encode(uint8_t *byte_array, uint8_t payload_length, uint8_t total_bits, uint8_t data_bits)
{
    uint16_t payload_length_bits = payload_length * 8;
    //             total bits after =           data bits + parity bits
    uint16_t total_bits_with_parity = payload_length_bits + ceil((double)payload_length/data_bits) * (total_bits - data_bits);
    uint8_t output_buffer_bytes = (uint8_t)ceil((double)total_bits_with_parity/8);
    uint8_t output_buffer[output_buffer_bytes];
    
    uint8_t payload_index, output_bit_index = 0;

    // 0 -> p1: i % total_bits == 0
    // 1 -> p2: i % total_bits == 1
    // 2 -> d1
    // 3 -> p4: i % total_bits == 3
    // 4 -> d2
    // 5 -> d3
    // 6 -> d4

    // Move data bits to output buffer
    for (uint16_t bit_index = 0; bit_index < total_bits_with_parity; bit_index++) 
    {
        if(!is_power_of_two(bit_index))
        {
            // This is a data bit, just copy it
            output_buffer[output_bit_index/8] |= byte_array[bit_index/8] & bit_index % 8;
        }
        output_bit_index++;
    }

    payload_index, output_bit_index = 0;
    // Calculate parity
    for (uint16_t bit_index = 0; bit_index < total_bits_with_parity; bit_index++) {
        if (is_power_of_two(bit_index))
        {
            // This is a parity bit, do maths
            for(uint16_t j = bit_index; j < bit_index / 7 + 7; j++)
            {
                if (!is_power_of_two(j))
                {
                    //XOR
                }
                // Loopa över alla databitar, parity beräknas på de databitar där 0bPARITY_IDX & 0bDATA_IDX == 1
                // Om j % 
            }
            output_buffer[output_bit_index] = ;
            output_bit_index++;
        }

    }
    
    return 0;
}

uint8_t is_power_of_two(uint16_t n) {
    // from https://www.geeksforgeeks.org/dsa/program-to-find-whether-a-given-number-is-power-of-2/
    // Check if n is positive and n & (n-1) is 0
    return (n > 0) && ((n & (n-1)) == 0);
}