#!/bin/sh

exec >> /var/log/pf9/bbmaster.log 2>&1

echo "Starting health check at $(date)"

# Perform the health check using curl and capture the HTTP status code
http_status=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 60 http://localhost:8082/v1/hosts)

# Log the HTTP status code
echo "HTTP status code: $http_status"

# Check if the HTTP status code is 200 (OK)
if [ "$http_status" -eq 200 ]; then
    echo "Health check passed. No action required."
else
    # Log that the health check failed
    echo "Health check failed. Restarting bbmaster."

    # Restart the bbmaster process
    supervisorctl restart bbmaster

    echo "bbmaster restarted."
fi

echo "Health check completed at $(date)"
exit 0
