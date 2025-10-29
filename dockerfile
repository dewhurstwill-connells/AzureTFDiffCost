FROM mcr.microsoft.com/azurelinux/base/python:3

# Copy files and install app dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Start the app.
CMD [ "python", "./main.py" ]