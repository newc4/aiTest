# coding=utf-8
import json
import enum
import time
from queue import Queue
import configure as conf

from env.ai_algorithm import AIAlgorithm

import logging
from env.multiagentenv import MultiAgentEnv
from csf_sdk import CSFInterface
from entities.parsing.complete_battle_state import CompleteBattleState

const = {
    "ENGINE": "engine",
    "BEGIN_GAME": "startGame"
}


class Direction(enum.IntEnum):
    NORTH = 0
    NORTHEAST = 1
    SOUTHEAST = 2
    SOUTH = 3
    SOUTHWEST = 4
    NORTHWEST = 5


class Logger():
    def print(self, round, message):
        print(str(round) + ' ' + str(message))


class SeaWarEnv(MultiAgentEnv):
    """The SeaWar environment for multi-agent micromanagement scenarios.
    """

    def __init__(
            self,
            debug=False,
            camp=1
    ):
        self.debug = debug
        self.queue = Queue(1)

        # Map arguments
        self.agents = {}
        self.enemies = {}
        self.n_agents = 0
        self.n_enemies = 0
        self.n_agents_id = []
        self.n_enemies_id = []
        # Actions
        self.n_actions_no_attack = 8
        self.n_actions_move = 6

        # create logger
        self._logger = logging.getLogger('seaLogger')
        self._logger.setLevel(logging.DEBUG)

        # create console handler and set level to debug
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter for console handler
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s')
        # add formatter to console handler
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

        self._init_failed = False
        self._scenario = None
        self._fetch_scenario_finish = False
        self._round = 1
        self._camp_id = camp
        self._game_started = False
        if camp == 1:
            self._sdk = CSFInterface(
                conf.ip, 1, conf.camp_id, conf.scenario_id, conf.seat_id)
            self._sdk.register(self._call_back)
            self._login_result = self._sdk.login(conf.username, conf.password)
            self._algorithm = AIAlgorithm(
                self._sdk, self._scenario, conf.camp_id, conf.scenario_id)
        elif camp == 2:
            self._sdk = CSFInterface(
                conf.ip, 1, conf.camp_id_2, conf.scenario_id, conf.seat_id_2)
            self._sdk.register(self._call_back)
            self._login_result = self._sdk.login(
                conf.username_2, conf.password_2)
            self._algorithm = AIAlgorithm(
                self._sdk, self._scenario, conf.camp_id_2, conf.scenario_id)
        else:
            raise NotImplementedError

        if self._login_result != 0:
            self._init_failed = True
            self._logger.info("AI1 登录失败")

        self._algorithm.set_logger(Logger())

        self._scenario, _ = self._sdk.fetchScenario()
        self._logger.info("_scenario_info:{}".format(self._scenario))
        self.map_x = int(self._scenario.war_map.cols)
        self.map_y = int(self._scenario.war_map.rows)
        for operator in self._scenario.operators:
            if operator._camp_id == self._camp_id:
                self.n_agents += 1
                self.n_agents_id.append(operator.operator_id)
            else:
                self.n_enemies += 1
                self.n_enemies_id.append(operator.operator_id)

        self.n_actions = self.n_actions_no_attack + self.n_enemies

    def _call_back(self, response):
        if "data" in response and "round" in response["data"]:
            self._round = response["data"]["round"]

        if response["type"] == const["BEGIN_GAME"]:
            self._logger.info(str(self._round) +
                              " callbackdata: %s" % response)
            if self._game_started:
                return
            self._game_started = True
            while not self._fetch_scenario_finish:
                time.sleep(0.1)
            send_result = self._sdk.battle_seat.sendNotDispatchTroops([])
        elif response["type"] == const["ENGINE"]:
            if response["data"]["judgements"]:
                self._logger.info(response["data"]["judgements"])
            self._battle_state = CompleteBattleState.parse(
                response, self._scenario, self._camp_id)
            self._algorithm.set_round(self._round)
            # set_attack_and_move
            if response["data"]["time_interval"] == 41501:
                self.update_units(self._battle_state)
                self.queue.put(False)
            # game_over
            elif response["data"]["time_interval"] == 70101:
                self._algorithm.make_decision(self._battle_state)
                self.queue.put(True)
            else:
                self._algorithm.make_decision(self._battle_state)
        else:
            if self.debug:
                self._logger.debug(str(self._round) +
                                   " callbackdata: %s " % response)

    def wait_attack_interval(self):
        return self.queue.get()

    def step(self, actions):
        actions_int = [int(a) for a in actions]
        # 发送机动，攻击计划
        plan_list = []
        if self.debug:
            logging.debug("Actions".center(60, "-"))
        for i, action in enumerate(actions_int):
            print(action)
            our_operator_id = self.n_agents_id[i]
            # our_operator = self._scenario._fetch_operator_by_id(our_operator_id)
            our_operator = self._battle_state.fetch_operator_by_id(
                our_operator_id)
            if our_operator is None:
                continue
            if not our_operator.asm_attack:
                continue
            asm_attack = our_operator.asm_attack[our_operator.state]
            our_operator_act_list = []
            if self.n_actions_no_attack - self.n_actions_move <= action < self.n_actions_no_attack:
                our_operator_path = []
                x, y = our_operator.position[0], our_operator.position[1]
                for _ in range(our_operator.move[our_operator.state]):
                    x, y = self.get_next_position(x, y, Direction(action - 2))
                    if self.check_bounds(x, y):
                        our_operator_path.append(str(x) + ',' + str(y))
                        pass
                    else:
                        break
                print(our_operator_path)
                our_operator_act_list = [
                    {"act_id": 2, "type": 402, "routes": our_operator_path}]
            is_formation = 0

            attack_list = []
            if self.n_actions_no_attack <= action < self.n_actions_no_attack + self.n_enemies:
                attack_list = [{"act_id": 1, "type": 502, "routes": [], "fp_operator_id": "",
                                "src_id": [str(our_operator_id)],
                                "target_id": [str(self.n_enemies_id[action - self.n_actions_no_attack])],
                                "aggressivity": str(30), "ammunition_num": 1,
                                "rounds": self._round, "is_suicide_attack": 0,
                                "support_operator_id": "", "land_position": "", "land_value": 0}]

            act_content = {"operator_id": str(our_operator_id), "camp": self._camp_id,
                           "seat": our_operator.seat_id,
                           "act_order": 1, "act_list": our_operator_act_list,
                           "attack_order": 1, "attack_list": attack_list}
            # 每个算子最多调用一次该接口，一次可以设置多个动作，act_list 设置机动动作，attack_list 设置攻击动作
            # print("ai 发送 一个作战计划")
            plan = {"type": 502, "operator_id": our_operator_id, "seat": our_operator.seat_id,
                    "act_order": 1, "is_formation": is_formation, "act_content": act_content}
            plan_list.append(plan)

        print(plan_list)
        self._logger.info(str(self._round) + "ai 发送 作战筹划 %s " % len(plan_list))
        # 在此时节，调用一次下方接口
        # 每个算子可以加plan_list中加一个plan，每个plan可以有多个机动动作、多个攻击动作
        maneuveringAttack = self._sdk.operator_seat.maneuveringAttack(
            plan_list)

    def get_agent_actions(self, agent_id, action):
        avail_actions = self.get_avail_agent_actions(agent_id)

    # Returns the available actions for agent_id.
    def get_avail_agent_actions(self, agent_id):
        operator = self._battle_state.fetch_operator_by_id(
            self.n_agents_id[agent_id])
        if operator and operator.state < 2:
            # cannot choose no-op when alive
            avail_actions = [0] * self.n_actions

            # stop should be allowed
            avail_actions[1] = 1
            # see if we can move
            if self.can_move(operator, Direction.NORTH):
                avail_actions[2] = 1
            if self.can_move(operator, Direction.NORTHEAST):
                avail_actions[3] = 1
            if self.can_move(operator, Direction.SOUTHEAST):
                avail_actions[4] = 1
            if self.can_move(operator, Direction.SOUTH):
                avail_actions[5] = 1
            if self.can_move(operator, Direction.SOUTHWEST):
                avail_actions[6] = 1
            if self.can_move(operator, Direction.NORTHWEST):
                avail_actions[7] = 1

            # Can attack only alive units that are alive in the shooting range
            if operator.asm_range:
                shoot_range = operator.asm_range[operator.state]

                for i, t_id in enumerate(self.n_enemies_id):

                    t_operator = self._battle_state.fetch_operator_by_id(t_id)
                    if t_operator and t_operator.state < 2 and t_operator.is_find == 1:
                        dist = self.distance(
                            operator.position[0], operator.position[1], t_operator.position[0], t_operator.position[1]
                        )
                        if dist <= shoot_range:
                            avail_actions[i + self.n_actions_no_attack] = 1

            return avail_actions

        else:
            # only no-op allowed
            return [1] + [0] * (self.n_actions - 1)

    # Whether a point is within the map bounds.
    def check_bounds(self, x, y):
        return 1 <= x <= self.map_x and 1 <= y <= self.map_y

    def get_next_position(self, x, y, direction):
        if direction == Direction.NORTH:
            x, y = x - 1, y
        elif direction == direction.NORTHEAST:
            (x, y) = (x, y + 1) if y % 2 == 0 else (
                x - 1, y + 1)
        elif direction == direction.SOUTHEAST:
            (x, y) = (x + 1, y + 1) if y % 2 == 0 else (
                x, y + 1)
        elif direction == direction.SOUTH:
            x, y = x + 1, y
        elif direction == direction.SOUTHWEST:
            (x, y) = (x + 1, y - 1) if y % 2 == 0 else (
                x, y - 1)
        elif direction == direction.NORTHWEST:
            (x, y) = (x, y - 1) if y % 2 == 0 else (
                x - 1, y - 1)
        return x, y

    # Whether a unit can move in a given direction.
    def can_move(self, operator, direction):
        x, y = self.get_next_position(
            operator.position[0], operator.position[1], direction)
        return self.check_bounds(x, y)

    # Distance between two points.
    @staticmethod
    def distance(y1, x1, y2, x2):
        du = x2 - x1
        dv = (y2 + x2 // 2) - (y1 + x1 // 2)
        return max(abs(du), abs(dv)) if ((du >= 0 and dv >= 0) or (du < 0 and dv < 0)) else abs(du) + abs(dv)

    # Reset the environment. Required after each full episode.
    def reset(self):
        if self._init_failed:
            self._logger.info(str(self._round) + "登录失败，请重试")
            return

        join_room_result = self._sdk.joinRoom()
        self._logger.info("join room:{}".format(join_room_result))

        self._algorithm.set_scenario(self._scenario)
        self._fetch_scenario_finish = True

    # Returns the size of the global state.
    def get_state_size(self):
        pass

    # Returns the size of the observation.
    def get_obs_size(self):
        pass

    # Returns the total number of actions an agent could ever take.
    def get_total_actions(self):
        return self.n_actions

    # Update units after an environment step. Not implemented.
    def update_units(self, battle_state):
        self.agents = battle_state.our_operators
        self.enemies = battle_state.enemy_operators
