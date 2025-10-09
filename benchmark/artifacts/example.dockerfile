# Example Dockerfile that passes the example.json rubric
FROM ubuntu:20.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update package list and install basic tools
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install Java 17 (meets the requirement for versions 11, 12, 13, or 17)
RUN apt-get update && apt-get install -y openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME environment variable
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Add Java to PATH (though it should already be there)
ENV PATH="$JAVA_HOME/bin:$PATH"

# Install JRuby
RUN curl -L https://repo1.maven.org/maven2/org/jruby/jruby-dist/9.3.10.0/jruby-dist-9.3.10.0-bin.tar.gz \
    -o jruby.tar.gz \
    && tar -xzf jruby.tar.gz \
    && mv jruby-9.3.10.0 /opt/jruby \
    && rm jruby.tar.gz

# Add JRuby to PATH
ENV PATH="/opt/jruby/bin:$PATH"

# Create the .ruby-version file with jruby-9.3
RUN echo "jruby-9.3.10.0" > /.ruby-version

# Create build.gradle file
RUN echo 'plugins {\n    id "java"\n}\n\nrepositories {\n    mavenCentral()\n}\n\ndependencies {\n    testImplementation "junit:junit:4.13.2"\n}' > /build.gradle

# Create spec directory
RUN mkdir -p /spec

# Set working directory
WORKDIR /

# Default command
CMD ["bash"]
