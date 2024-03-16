FROM python:3.9-alpine

# Copy application
COPY ./ /app/

# Update and run pip for python dependencies
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Enable cron task
COPY ./cron /app/cron
RUN crontab /app/cron

# Run cron when the container is started
CMD ["crond", "-f"]