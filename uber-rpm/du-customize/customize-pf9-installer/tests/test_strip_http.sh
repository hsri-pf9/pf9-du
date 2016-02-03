source $(dirname $0)/../proxy.sh

TEST_HOSTS=(
            "http://squid.pf9.company.com"
            "https://squid.pf9.company.com"
            "http://squid.pf9.company.com:1234"
            "https://squid.pf9.company.com:3128"
            "pf9.http://a.company.com"
            "pf9.https://a.company.com"
            "squid.company.com"
            "squid.company.com:1234"
            "https.company.com:1234"
            "http.company.com"
            )

for host in "${TEST_HOSTS[@]}"
do
    host_done=$(strip_http_schema "${host}")
    if echo $host_done | grep -E -q "^https?://"; then
        echo "ERROR: $host_done "
        exit 1
    else
        echo "OK: $host_done"
    fi
done
