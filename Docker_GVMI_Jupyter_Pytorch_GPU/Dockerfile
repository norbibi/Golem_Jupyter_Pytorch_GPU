FROM maugnorbert/docker_golem_nvidia:535.98

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
	openssh-server \
	python3-pip \
	python3-venv \
	htop \
	curl \
	wget \
	git \
	sshfs \
	nano \
	build-essential \
	&& rm -rf /var/lib/apt/lists/*

RUN cd /root \
	&& wget https://developer.download.nvidia.com/compute/cuda/12.2.1/local_installers/cuda_12.2.1_535.86.10_linux.run \
	&& chmod +x cuda_12.2.1_535.86.10_linux.run \
	&& sh cuda_12.2.1_535.86.10_linux.run --toolkit --silent \
	&& rm cuda_12.2.1_535.86.10_linux.run \
	&& ldconfig

RUN mkdir -p /run/sshd

RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    ssh-keygen -A

RUN echo 'cd /golem/work' >> /root/.bashrc

COPY proxychains4 /usr/bin/proxychains4
COPY libproxychains4.so /usr/lib/libproxychains4.so
COPY proxychains.conf /etc/proxychains.conf

ENV TMPDIR=/tmp PIP_PROGRESS_BAR=off PROXYCHAINS_QUIET_MODE=1

RUN python3 -m venv /root/venv
RUN /root/venv/bin/pip install --upgrade pip && \
	/root/venv/bin/pip install wheel setuptools notebook torch torchvision torchaudio pytorch-lightning lightning pandas seaborn && \
	rm -rf /root/.cache/pip

RUN mkdir -p /root/venv/share/jupyter/lab/settings/
COPY overrides.json /root/venv/share/jupyter/lab/settings/overrides.json

WORKDIR /golem/work

CMD blob
