#!/usr/bin/env python3

import asyncio
from datetime import datetime, timedelta
import pathlib
import random
import string
import subprocess
import colorama
import argparse
import os
import threading

from yapapi import Golem
from yapapi.contrib.service.socket_proxy import SocketProxy, SocketProxyService
from yapapi.payload import vm
from yapapi.log import enable_default_logger
from yapapi.props import inf, com
from yapapi import __version__ as yapapi_version
from yapapi.services import ServiceState

TEXT_COLOR_CYAN = "\033[36;1m"
TEXT_COLOR_YELLOW = "\033[33;1m"
TEXT_COLOR_DEFAULT = "\033[0m"

STARTING_TIMEOUT = timedelta(minutes=10)

password = None
sslp = None

def print_env_info(golem: Golem):
    print(
        f"yapapi version: {TEXT_COLOR_YELLOW}{yapapi_version}{TEXT_COLOR_DEFAULT}\n"
        f"Using subnet: {TEXT_COLOR_YELLOW}{golem.subnet_tag}{TEXT_COLOR_DEFAULT}, "
        f"payment driver: {TEXT_COLOR_YELLOW}{golem.payment_driver}{TEXT_COLOR_DEFAULT}, "
        f"and network: {TEXT_COLOR_YELLOW}{golem.payment_network}{TEXT_COLOR_DEFAULT}\n"
    )

def thread_ssh_cmd(cmd):
    while(1):
        subprocess.call(cmd, shell=True)
        print("Command finished: " + cmd)

def cmds_add_ram_overlay(size_gbytes):
    return ["mkdir /overlay /newroot /oldroot",
            f"mount -t tmpfs -o size={size_gbytes}g tmpfs /overlay",
            "mkdir /overlay/upper /overlay/work",
            "mount -t overlay overlay -o lowerdir=/,upperdir=/overlay/upper,workdir=/overlay/work /newroot",
            "mount -o bind /proc /newroot/proc",
            "mount -o bind /sys /newroot/sys",
            "mount -o bind /dev /newroot/dev",
            "mount -o bind /dev/pts /newroot/dev/pts",
            "mount -o bind /tmp /newroot/tmp",
            "cd /newroot && pivot_root . oldroot && exec chroot .",
            "umount /oldroot/proc",
            "umount /oldroot/tmp",
            "umount -l /oldroot/sys",
            "umount -l /oldroot/dev/pts",
            "umount -l /oldroot/dev"]

def run_cmds(script, cmds):
    for cmd in cmds:
        script.run("/bin/bash", "-c", cmd)

class JupyterService(SocketProxyService):
    def __init__(self, proxy: SocketProxy):
        self.proxy = proxy
        self.ssh_remote_port = 22
        super().__init__()

    @staticmethod
    async def get_payload():
        return await vm.repo(
            image_hash="a3b192b0773df28356ee0595ae66d0b70e0974d5e4db8bd4a098617e",
            image_url="http://82.66.219.1/docker-docker_gvmi_jupyter_pytorch_gpu-latest-fedc753ea5.gvmi",
            min_mem_gib=args.min_mem_gib,
            min_storage_gib=args.min_storage_gib,
            min_cpu_threads=args.min_cpu_threads,
            capabilities=[vm.VM_CAPS_VPN, "cuda"]
        )

    async def start(self):
        async for script in super().start():
            yield script

        global password
        global sslp

        password = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(8))

        script = self._ctx.new_script(timeout=timedelta(minutes=10))

        run_cmds(script, cmds_add_ram_overlay(8))

        script.run("/bin/bash", "-c", f'echo -e "{password}\n{password}" | passwd')
        script.run("/bin/bash", "-c", "modprobe fuse")
        script.run("/bin/bash", "-c", "/usr/sbin/sshd &")

        yield script

        server_ssh = await self.proxy.run_server(self, self.ssh_remote_port)
        sslp = server_ssh.local_port

        script = self._ctx.new_script(timeout=timedelta(hours=24))

        script.run("/bin/bash", "-c", "cd /golem/work && proxychains4 /root/venv/bin/jupyter-notebook --port=5555 --allow-root --NotebookApp.token='' --NotebookApp.password='' --ServerApp.terminado_settings=\"shell_command=['/bin/bash']\" > /dev/null 2>&1 &")

        yield script

async def main(subnet_tag, payment_driver=None, payment_network=None, shared_folder=None, num_instances=1):

    async with Golem(
        budget=10,
        subnet_tag=subnet_tag,
        payment_driver=payment_driver,
        payment_network=payment_network,
    ) as golem:

        print_env_info(golem)
        commissioning_time = datetime.now()

        network = await golem.create_network("192.168.0.1/24")
        proxy = SocketProxy(ports=range(2222, 2222 + 1))
        cluster = await golem.run_service(
            JupyterService,
            network=network,
            num_instances=num_instances,
            instance_params=[{"proxy": proxy} for _ in range(num_instances)]
        )

        instances = cluster.instances

        def still_starting():
            return any(i.state in (ServiceState.pending, ServiceState.starting) for i in instances)

        while still_starting() and datetime.now() < commissioning_time + STARTING_TIMEOUT:
            print(f"instances: {instances}")
            await asyncio.sleep(5)

        if still_starting():
            raise Exception(
                f"Failed to start instances after {STARTING_TIMEOUT.total_seconds()} seconds"
            )

        cmds = []

        if shared_folder != "":
            cmds.append(f"dpipe /usr/lib/openssh/sftp-server = sshpass -p {password} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@127.0.0.1 -p {sslp} sshfs :{shared_folder} /golem/work -o slave")

        cmds.append(f"sshpass -p {password} ssh -N -L localhost:5555:localhost:5555 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@127.0.0.1 -p {sslp}")

        for redondant in range(8080, 8090):
            cmds.append(f"sshpass -p {password} ssh -N -R {redondant} -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@127.0.0.1 -p {sslp}")

        print(f"sshpass -p {password} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@127.0.0.1 -p {sslp}")

        for cmd in cmds:
            threading.Thread(target=thread_ssh_cmd, args=(cmd,)).start()

        print(f"{TEXT_COLOR_CYAN}Jupyter Notebook available at http://localhost:5555{TEXT_COLOR_DEFAULT}")

        while True:
            print(instances)
            try:
                await asyncio.sleep(10)

            except (KeyboardInterrupt, asyncio.CancelledError):
                break

        await proxy.stop()
        cluster.stop()
        await network.remove()

if __name__ == "__main__":

    colorama.init()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--subnet-tag",
        type=str,
        default="norbert"
    )
    parser.add_argument(
        "--payment-driver",
        type=str,
        default="erc20"
    )
    parser.add_argument(
        "--payment-network",
        type=str,
        default="goerli"
    )
    parser.add_argument(
        "--shared-folder",
        type=str,
        default=""
    )
    parser.add_argument(
        "--min-mem-gib",
        type=int,
        default=20
    )
    parser.add_argument(
        "--min-storage-gib",
        type=int,
        default=64
    )
    parser.add_argument(
        "--min-cpu-threads",
        type=int,
        default=8
    )
    args = parser.parse_args()

    #now = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    log_file=f"jupyter_pytorch.log"

    enable_default_logger(
        debug_activity_api=True,
        debug_market_api=True,
        debug_payment_api=True,
        debug_net_api=True,
        log_file=log_file,
    )

    if args.shared_folder:
        shared_folder = os.path.abspath(args.shared_folder)
    else:
        shared_folder = ""

    loop = asyncio.get_event_loop()
    task = loop.create_task(
        main(
            subnet_tag=args.subnet_tag,
            payment_driver=args.payment_driver,
            payment_network=args.payment_network,
            shared_folder=shared_folder))

    try:
        loop.run_until_complete(task)
        print(
            f"{TEXT_COLOR_YELLOW}Shutdown completed, thank you for waiting!{TEXT_COLOR_DEFAULT}"
        )
    except:
        pass

# ./Jupyter_Pytorch_GPU.py --shared-folder=./shared