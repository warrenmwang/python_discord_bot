# Use a small base image
# FROM alpine:3.14
FROM ubuntu:latest

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the conda package manager
RUN bash /app/Anaconda3-2022.10-Linux-x86_64.sh -b -p /app/bin/anaconda3 && \
    rm Anaconda3-2022.10-Linux-x86_64.sh

# Set the PATH variable to include the location of the conda package manager
ENV PATH="/app/bin/anaconda3/bin:$PATH"

# Create a conda environment with the specified dependencies
RUN conda env create -f environment.yml

# get ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Run the main.py script
CMD ["/app/bin/anaconda3/envs/discord_bot/bin/python", "main.py"]
