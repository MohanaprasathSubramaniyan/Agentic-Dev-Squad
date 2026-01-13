# Start with the lightweight Python image
FROM python:3.11-slim

# Install the Data Science tools
RUN pip install pandas matplotlib scipy

# Set the working directory
WORKDIR /app