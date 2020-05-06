from env import SeaWarEnv
import numpy as np
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--camp', type=int, default=1, help='None')
    args = parser.parse_args()

    if (args.camp == 1):
        env = SeaWarEnv(camp = 1)
    elif (args.camp == 2):
        env = SeaWarEnv(camp = 2)
    else:
        raise NotImplementedError

    env_info = env.get_env_info()
    n_actions = env_info["n_actions"]
    n_agents = env_info["n_agents"]

    n_episodes = 1
    for e in range(n_episodes):
        env.reset()
        terminated = False
        while not terminated:
            terminated = env.wait_attack_interval()
            if terminated == True:
                break
            else:
                actions = []
                # 每次作战筹划时节前，获得每个agent当前环境下可执行的动作列表（目前包括静止、向各个方向移动以及攻击，后续可继续添加动作），并在列表中随机选择一个动作执行
                for agent_id in range(n_agents):
                    avail_actions = env.get_avail_agent_actions(agent_id)

                    avail_actions_ind = np.nonzero(avail_actions)[0]
                    action = np.random.choice(avail_actions_ind)

                    actions.append(action)
                env.step(actions)

if __name__ == "__main__":
    main()