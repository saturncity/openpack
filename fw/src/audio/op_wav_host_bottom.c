/* Host side of the WAV backend. Built into the native simulator runner. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "op_wav_host.h"

#define RATE 48000u

static FILE *out_fp;
static uint32_t out_bytes;

static void put32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = v >> (8 * i); }
static void put16(uint8_t *p, uint16_t v) { p[0] = v; p[1] = v >> 8; }
static uint32_t get32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t get16(const uint8_t *p) { return p[0] | p[1] << 8; }

static void make_header(uint8_t h[44], uint32_t data_bytes)
{
	memcpy(h, "RIFF", 4); put32(h + 4, 36 + data_bytes);
	memcpy(h + 8, "WAVEfmt ", 8); put32(h + 16, 16);
	put16(h + 20, 1); put16(h + 22, 1); put32(h + 24, RATE);
	put32(h + 28, RATE * 2); put16(h + 32, 2); put16(h + 34, 16);
	memcpy(h + 36, "data", 4); put32(h + 40, data_bytes);
}

int op_wav_host_load(const char *path, short **buf, unsigned long *n)
{
	FILE *f = fopen(path, "rb");
	uint8_t h[12], c[8], fmt[16];
	int fmt_ok = 0, rc = -1;

	*buf = NULL; *n = 0;
	if (!f) return -1;
	if (fread(h, 1, 12, f) != 12 || memcmp(h, "RIFF", 4) || memcmp(h + 8, "WAVE", 4)) goto out;
	while (fread(c, 1, 8, f) == 8) {
		uint32_t sz = get32(c + 4);
		if (!memcmp(c, "fmt ", 4) && sz >= 16) {
			if (fread(fmt, 1, 16, f) != 16) goto out;
			fmt_ok = get16(fmt) == 1 && get16(fmt + 2) == 1 &&
				 get32(fmt + 4) == RATE && get16(fmt + 14) == 16;
			if (!fmt_ok) goto out;
			if (fseek(f, (long)(sz - 16 + (sz & 1)), SEEK_CUR)) goto out;
		} else if (!memcmp(c, "data", 4) && fmt_ok) {
			short *b = malloc(sz ? sz : 2);
			if (!b) goto out;
			if (fread(b, 1, sz, f) != sz) { free(b); goto out; }
			*buf = b; *n = sz / 2; rc = 0;
			goto out;
		} else if (fseek(f, (long)(sz + (sz & 1)), SEEK_CUR)) {
			goto out;
		}
	}
out:
	fclose(f);
	return rc;
}

void op_wav_host_free(void *buf) { free(buf); }

int op_wav_host_save(const char *path, const short *buf, unsigned long n)
{
	uint8_t h[44];
	FILE *f = fopen(path, "wb");

	if (!f) return -1;
	make_header(h, (uint32_t)(n * 2));
	int ok = fwrite(h, 1, 44, f) == 44 && fwrite(buf, 2, n, f) == n;
	return (fclose(f) == 0 && ok) ? 0 : -1;
}

int op_wav_host_out_open(const char *path)
{
	uint8_t h[44];

	if (out_fp) fclose(out_fp);
	out_bytes = 0;
	out_fp = fopen(path, "wb");
	if (!out_fp) return -1;
	make_header(h, 0);
	return fwrite(h, 1, 44, out_fp) == 44 && fflush(out_fp) == 0 ? 0 : -1;
}

int op_wav_host_out_append(const short *buf, unsigned long n)
{
	uint8_t h[44];

	if (!out_fp) return -1;
	if (fwrite(buf, 2, n, out_fp) != n) return -1;
	out_bytes += (uint32_t)(n * 2);
	make_header(h, out_bytes);
	if (fseek(out_fp, 0, SEEK_SET) || fwrite(h, 1, 44, out_fp) != 44 ||
	    fseek(out_fp, 0, SEEK_END) || fflush(out_fp)) return -1;
	return 0;
}

const char *op_wav_host_getenv(const char *name) { return getenv(name); }
