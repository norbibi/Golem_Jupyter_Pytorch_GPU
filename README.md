# Golem_Jupyter_Pytorch_GPU (Linux only)

This application is a preview of the 'Golem Jupyter' PoC with GPU providers while waiting for its official release.

Additionnal Features:
 - requestor folder sharing
 - requestor networking sharing
 - writable filesystem (to add package for example)

Requirements:
  - golem requestor: https://handbook.golem.network/requestor-tutorials/flash-tutorial-of-requestor-development
  - sshpass and vde2 packages (Ubuntu)

I leave 2 providers available on the testnet network (15 threads, 24GB RAM, 600GB storage, RTX3090).  
An example of classification (from MNIST dataset) is included.

How to use:
``` 
git clone https://github.com/norbibi/Golem_Jupyter_Pytorch_GPU.git
cd Golem_Jupyter_Pytorch_GPU
./Jupyter_Pytorch_GPU.py --shared-folder=./shared
``` 

Enjoy :)
