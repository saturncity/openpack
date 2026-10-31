/* Host-side WAV helpers (native "bottom" layer: plain libc, no Zephyr headers).
 * 48 kHz mono 16-bit PCM only, little-endian host assumed. Return 0 or -1. */
#ifndef OP_WAV_HOST_H
#define OP_WAV_HOST_H

/* Load whole file; *buf is host-malloc'd, release with op_wav_host_free(). */
int op_wav_host_load(const char *path, short **buf, unsigned long *n);
void op_wav_host_free(void *buf);
/* Write a complete WAV file. */
int op_wav_host_save(const char *path, const short *buf, unsigned long n);
/* Streaming output: header is kept valid after every append. One output at a time. */
int op_wav_host_out_open(const char *path);
int op_wav_host_out_append(const short *buf, unsigned long n);
/* getenv passthrough (path overrides). */
const char *op_wav_host_getenv(const char *name);

#endif
