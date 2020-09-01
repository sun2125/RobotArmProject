import fulcrane
import numpy as np
import asyncio
from numpy import linalg as LA
import sys

async def main():
    ip = '192.168.0.51'
    controller = await fulcrane.Controller.create(ip)
    def position_callback(pos):
        with open("angle_data.txt","w") as f:
            f.write(f"{pos[4]:.16f},{pos[3]:.16f},{pos[5]:.16f}\n")
        # sys.stdout.write(f"{pos[3]:.16f},{pos[4]:.16f},{pos[5]:.16f}\n")
        # sys.stdout.flush()
        return False
    await controller.notify_joint_angle(position_callback, timeout=50)
    controller.transport.close()

if __name__=="__main__":
    asyncio.run(main())
