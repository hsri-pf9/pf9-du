#!/bin/sh

exec >> /var/log/pf9/bbmaster.log 2>&1

# Usage: log_message "Your message here"
log_message() {
    message=$1

    # Get current date and time
    current_time=$(date "+%Y-%m-%d %H:%M:%S")

    # Append the message to the logfile with a timestamp
    echo "[$current_time] liveness_probe:: $message"
}

log_message "starting health check"

# Perform the health check using curl and capture the HTTP status code
http_status=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 60 http://localhost:18082/v1/hosts)

# Log the HTTP status code
log_message "status check returned code: $http_status"

# Check if the HTTP status code is 200 (OK)
if [ "$http_status" -eq 200 ]; then
    log_message "health check passed. No action required"
else
    # Log that the health check failed
    log_message "health check failed. Restarting bbmaster"

    # Restart the bbmaster process
    supervisorctl restart bbmaster

    log_message "bbmaster restarted"
fi

log_message "health check completed"
exit 0
