FROM ubuntu:latest
LABEL authors="Kuroko"

ENTRYPOINT ["top", "-b"]