#!/usr/bin/env bash
# 给 GitHub 替身(fake_github.py)造一套证书:一张一次性 CA + 一张 api.github.com / github.com 的服务端证书。
#
# track opendesign-in-app-update-install §3。**这张 CA 只在用完就扔的 Windows runner 上被信任**
# (导进那台机器的受信根,job 结束机器就没了),别的地方谁都不信它。
#
# 为什么是正经的"CA + 叶子"而不是一张自签叶子:python 3.13 起默认开 VERIFY_X509_STRICT,
# 自签叶子当信任锚会被拒。产品内嵌的是 3.12,但别让测试替身赌版本。
# 本机判据 tests/test_update_e2e_harness.py 用同一个脚本造证书、真握一次手(并显式开 STRICT)。
#
# 用法:make-e2e-certs.sh <输出目录>   产出 ca.crt server.crt server.key
set -euo pipefail

OUT="${1:?用法: make-e2e-certs.sh <输出目录>}"
mkdir -p "$OUT"
cd "$OUT"

cat > ca.cnf <<'CNF'
[req]
distinguished_name = dn
prompt = no
x509_extensions = v3_ca
[dn]
CN = OpenDesign e2e throwaway CA
[v3_ca]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
CNF

cat > server.cnf <<'CNF'
[req]
distinguished_name = dn
prompt = no
[dn]
CN = api.github.com
[v3_srv]
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:api.github.com, DNS:github.com
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
CNF

openssl req -x509 -new -newkey rsa:2048 -nodes -days 2 \
  -keyout ca.key -out ca.crt -config ca.cnf 2>/dev/null
openssl req -new -newkey rsa:2048 -nodes \
  -keyout server.key -out server.csr -config server.cnf 2>/dev/null
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -days 2 -out server.crt -extfile server.cnf -extensions v3_srv 2>/dev/null

# CA 私钥用完即删:服务端只需要叶子的私钥,留着 CA 私钥只会多一个能签别的域名的东西。
rm -f ca.key server.csr ca.srl ca.cnf server.cnf
echo "certs: $(ls)"
