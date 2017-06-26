import gym
import gym_unrealcv
import time
from distutils.dir_util import copy_tree
import os
import json
import random
import numpy as np
import cv2
from constants import *
import keras.backend as K
from ddpg import DDPG
import io_util
from gym import wrappers
import time


if __name__ == '__main__':

    env = gym.make(ENV_NAME)

    ACTION_SIZE = len(env.action)

    #init log file
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
    if not os.path.exists(PARAM_DIR):
        os.makedirs(PARAM_DIR)

    Agent = DDPG(ACTION_SIZE, MEMORY_SIZE, GAMMA,
                 LEARNINGRATE_CRITIC, LEARNINGRATE_ACTOR, TARGET_UPDATE_RATE,
                 INPUT_SIZE, INPUT_SIZE, INPUT_CHANNELS)
    #load init param
    if not CONTINUE:
        explorationRate = INITIAL_EPSILON
        current_epoch = 0
        stepCounter = 0
        loadsim_seconds = 0
        env = wrappers.Monitor(env, MONITOR_DIR + 'tmp', write_upon_reset=True,force=True)

    else:
        #Load weights, monitor info and parameter info.
        with open(params_json) as outfile:
            d = json.load(outfile)
            explorationRate = d.get('explorationRate')
            current_epoch = d.get('current_epoch')
            stepCounter = d.get('stepCounter')
            loadsim_seconds = d.get('loadsim_seconds')
            Agent.loadWeights(critic_weights_path, actor_weights_path)
            io_util.clear_monitor_files(MONITOR_DIR + 'tmp')
            copy_tree(monitor_path, MONITOR_DIR + 'tmp')
            env = wrappers.Monitor(env, MONITOR_DIR + 'tmp', write_upon_reset=True,resume=True)

    if not os.path.exists(TRA_DIR):
        io_util.create_csv_header(TRA_DIR)

    try:
        start_time = time.time()
        for epoch in xrange(current_epoch + 1, MAX_EPOCHS + 1, 1):
            obs_new = env.reset()
            obs_last = obs_new
            observation = io_util.preprocess_img(obs_new,obs_last)
            motion = [0,0]
            cumulated_reward = 0
            if ((epoch) % TEST_INTERVAL_EPOCHS != 0 or stepCounter < LEARN_START_STEP) and TRAIN is True :  # explore
                EXPLORE = True
            else:
                EXPLORE = False
                print ("Evaluate Model")
            for t in xrange(MAX_STEPS_PER_EPOCH):

                start_req = time.time()


                if EXPLORE is True: #explore

                    action_pred = Agent.actor.model.predict(observation)
                    action = Agent.Action_Noise(action_pred, explorationRate)
                    action_env = ( action[0] * VELOCITY_MAX,
                              (action[1]-0.5) * ANGLE_MAX,
                              action[2])

                    obs_new, reward, done, info = env.step(action_env)
                    newObservation = io_util.preprocess_img(obs_new,obs_last)
                    #print newObservation.shape

                    stepCounter += 1

                    Agent.addMemory(observation, action, reward, newObservation, done)

                    observation = newObservation
                    obs_last = obs_new
                    motion = action[:2]
                    if stepCounter == LEARN_START_STEP:
                        print("Starting learning")


                    if Agent.getMemorySize() >= LEARN_START_STEP:
                        Agent.learnOnMiniBatch(BATCH_SIZE)
                        if explorationRate > FINAL_EPSILON and stepCounter > LEARN_START_STEP:
                            explorationRate -= (INITIAL_EPSILON - FINAL_EPSILON) / MAX_EXPLORE_STEPS
                #test
                else:
                    action = Agent.actor.model.predict(observation)
                    obs_new, reward, done, info = env.step(action)
                    newObservation = io_util.preprocess_img(obs_new)
                    observation = newObservation

                #print 'step time:' + str(time.time() - start_req)
                if SHOW:
                    io_util.show_info(info, obs_new)
                if MAP:
                    io_util.live_plot(info)
                io_util.save_trajectory(info, TRA_DIR, epoch)

                cumulated_reward += reward
                if done:
                    m, s = divmod(int(time.time() - start_time + loadsim_seconds), 60)
                    h, m = divmod(m, 60)

                    print ("EP " + str(epoch) +" Csteps= " + str(stepCounter) + " - {} steps".format(t + 1) + " - CReward: " + str(
                        round(cumulated_reward, 2)) + "  Eps=" + str(round(explorationRate, 2)) + "  Time: %d:%02d:%02d" % (h, m, s) )
                        # SAVE SIMULATION DATA
                    if (epoch) % SAVE_INTERVAL_EPOCHS == 0 and TRAIN is True:
                        # save model weights and monitoring data
                        print 'Save model'
                        Agent.saveModel( MODEL_DIR + '/ep' +str(epoch))

                        copy_tree(MONITOR_DIR + 'tmp', MONITOR_DIR + str(epoch))
                        # save simulation parameters.
                        parameter_keys = ['explorationRate', 'current_epoch','stepCounter', 'FINAL_EPSILON','loadsim_seconds']
                        parameter_values = [explorationRate, epoch, stepCounter,FINAL_EPSILON, int(time.time() - start_time + loadsim_seconds)]
                        parameter_dictionary = dict(zip(parameter_keys, parameter_values))
                        with open(PARAM_DIR + '/' + str(epoch) + '.json','w') as outfile:
                            json.dump(parameter_dictionary, outfile)

                    break

    except KeyboardInterrupt:
        print("Shutting down")
        env.close()