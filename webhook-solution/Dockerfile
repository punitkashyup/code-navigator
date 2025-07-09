# Stage 1: Build git binary
FROM amazonlinux:2 as git-installer

RUN yum update -y && \
    yum install -y git && \
    yum clean all

# Stage 2: Lambda image
FROM public.ecr.aws/lambda/python:3.12

# Copy git from the builder image
COPY --from=git-installer /usr/bin/git /usr/bin/git
COPY --from=git-installer /usr/libexec/git-core /usr/libexec/git-core
COPY --from=git-installer /usr/lib64/libpcre2-8.so.0 /usr/lib64/
COPY --from=git-installer /usr/share/git-core /usr/share/git-core

# Copy function code
COPY lambda_code_updater.py opensearch_ops.py lambda_webhook_handler.py ./
COPY src/code_splitter ./src/code_splitter

# Install dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt --target .

# Set the CMD to your handler (filename.handler_function)
CMD [ "lambda_webhook_handler.lambda_handler" ]

#local setup
# EXPOSE 8000
# CMD [ "python", "simple_webhook_server.py" ]