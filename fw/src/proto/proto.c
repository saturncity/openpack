#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "proto.h"

uint16_t op_status_pack(const struct op_telem *t)
{
	int bat = t->bat_pct > 100 ? 100 : t->bat_pct;
	int pk = 63 + (t->peak_dbfs > 0 ? 0 : t->peak_dbfs < -63 ? -63 : t->peak_dbfs);

	return (uint16_t)(bat | (pk << 7) | ((t->flags & 7) << 13));
}

void op_status_unpack(uint16_t w, struct op_telem *t)
{
	t->bat_pct = w & 0x7f;
	t->peak_dbfs = (int8_t)(((w >> 7) & 0x3f) - 63);
	t->flags = (w >> 13) & 7;
}

int op_parse_int(const char *s, long lo, long hi, long *v)
{
	char *e;
	long x;

	if (!*s) {
		return -1;
	}
	x = strtol(s, &e, 10);
	if (*e || x < lo || x > hi) {
		return -1;
	}
	*v = x;
	return 0;
}

int op_parse_tenths(const char *s, int limit, int *tenths)
{
	int neg = 0, whole = 0, frac = 0, digits = 0;

	if (*s == '-' || *s == '+') {
		neg = *s++ == '-';
	}
	for (; isdigit((unsigned char)*s); s++, digits++) {
		whole = whole * 10 + (*s - '0');
		if (whole > 1000) {
			return -1;
		}
	}
	if (*s == '.') {
		s++;
		if (isdigit((unsigned char)*s)) {
			frac = *s++ - '0';
			digits++;
		}
		while (isdigit((unsigned char)*s)) { /* extra decimals truncate */
			s++;
		}
	}
	if (*s || !digits) {
		return -1;
	}
	whole = whole * 10 + frac;
	if (whole > limit) {
		return -1;
	}
	*tenths = neg ? -whole : whole;
	return 0;
}

size_t op_proto_exec(const struct op_cmd *tbl, size_t n, void *ctx, char *line, char *out, size_t outsz)
{
	char *argv[OP_PROTO_MAX_ARGS];
	int argc = 0;
	char *p = line, *body = out + 2;
	const char *err = "unknown command";
	size_t len;

	while (*p) {
		while (*p && isspace((unsigned char)*p)) {
			*p++ = 0;
		}
		if (!*p) {
			break;
		}
		if (argc == OP_PROTO_MAX_ARGS) {
			return (size_t)snprintf(out, outsz, "err too many args\n");
		}
		argv[argc++] = p;
		while (*p && !isspace((unsigned char)*p)) {
			p++;
		}
	}
	if (!argc) {
		return 0;
	}
	for (size_t i = 0; i < n; i++) {
		if (!strcmp(argv[0], tbl[i].name)) {
			body[0] = 0;
			err = tbl[i].fn(ctx, argc - 1, argv + 1, body, outsz - 2 - 2);
			break;
		}
	}
	if (err) {
		return (size_t)snprintf(out, outsz, "err %s\n", err);
	}
	memcpy(out, "ok", 2);
	len = strlen(body);
	body[len] = '\n';
	body[len + 1] = 0;
	return len + 3;
}
