# Use an official Python image as the base.
FROM python:3.10

# Set the working directory inside the container.
WORKDIR /app

# Set environment variables to accept the EULA and force non-interactive mode.
ENV ACCEPT_EULA=Y
ENV DEBIAN_FRONTEND=noninteractive

# Install the ODBC driver for SQL Server and its dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    apt-transport-https \
    unixodbc-dev \
    gnupg2 \
    curl \
    # Add the Microsoft ODBC repository and key using a trusted method.
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/11/prod bullseye main" > /etc/apt/sources.list.d/mssql-prod.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    msodbcsql17 \
    # Clean up to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container.
COPY requirements.txt .

# Install the Python dependencies listed in requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project files into the container.
COPY . .