"""This code borrows elements from: 

[1] http://deeplearning.net/tutorial/logreg.html
[2] http://deeplearning.net/tutorial/mlp.html
[3] http://deeplearning.net/tutorial/lenet.html
"""
import sys
import numpy as np
from theano.tensor.nnet import conv
from theano.tensor.nnet import conv2d

from theano.tensor.signal import downsample
from theano.tensor.signal import pool
import theano
import theano.tensor as T
import os
import scipy.ndimage
import scipy.misc


from SRCNN_Layers import *

def train_SRCNN(train_set_x,train_set_y,valid_set_x,valid_set_y,test_set_x,test_set_y,
    n_train_batches, n_valid_batches, n_test_batches, n_epochs, batch_size,lr,l2=0,upsampling_factor=4):
    #Assume x to be shape (batch_size,3,33,33)
    x = T.matrix('x')
    y = T.matrix('y')

    theano.config.optimizer = 'fast_compile'
    print "theano optimizer: " + str(theano.config.optimizer)

    rng = np.random.RandomState(11111)
    index = T.lscalar() 

    reshaped_input = x.reshape((batch_size,3,33,33))# / 255
    reshaped_gt = y.reshape((batch_size,3,33,33)) #/ 255

    learning_rate = theano.shared(np.cast[theano.config.floatX](lr))

    #Upsampling layer now done in preprocessing to save compute
    #upsampled_input = T.nnet.abstract_conv.bilinear_upsampling(reshaped_input,upsampling_factor,batch_size=batch_size,num_input_channels=3)
    # r_fun = theano.function([index],upsampled_input.shape,givens = {
    #         x: train_set_x[index * batch_size: (index + 1) * batch_size]
    #         })
    # theano.printing.debugprint(r_fun(0))
    
    #Filter params
    f1 = 9
    f2 = 1
    f3 = 5
    output_len = 33 - f1 - f2 - f3 + 3
    #Conv for Patch extraction
    conv1 = Conv_Layer_ReLU(rng, reshaped_input, image_shape=(batch_size,3,33,33),filter_shape = (64,3,f1,f1))
    conv1_len = 33 - f1 + 1 
    #Conv for Non linear mapping

    conv2 = Conv_Layer_ReLU(rng, conv1.output, image_shape=(batch_size,64,conv1_len,conv1_len),filter_shape = (32,64,f2,f2))
    conv2_len = conv1_len - f2 + 1
    #Conv for Reconstruction
    conv3 = Conv_Layer_None(rng, conv2.output, image_shape=(batch_size,32,conv2_len,conv2_len),filter_shape = (3,32,f3,f3))
    model_output = conv3.output
    model_output_clipped = T.clip(model_output,0.0,1.0)

    params = conv3.params + conv2.params + conv1.params

    #grab center pixels
    center_start = (33 - output_len) / 2
    center_end = 33 - center_start
    sub_y = reshaped_gt[:,:,center_start:center_end,center_start:center_end]

    #MSE between center pixels of prediction and ground truth
    #cost = 1.0/batch_size * T.sum((sub_y-model_output) ** 2) 

    regularization = 0
    for param in params:
        regularization += T.sum(param[0] ** 2)

    cost = T.mean((sub_y - model_output) ** 2) 

    #PNSR without clipped output
    #PSNR of a patch is based on color space
    MSE_per_pixel = cost#/(output_len*output_len*3)
    psnr = 20 * T.log10(255) - 10 * T.log10(MSE_per_pixel)
    cost += l2 * regularization
    reconstucted_imgs = model_output

    #PSNR of a patch is based on color space
    # MSE_per_pixel = cost/(output_len*output_len*3)
    # psnr = 20 * T.log10(1) - 10 * T.log10(MSE_per_pixel)
    # reconstucted_imgs = model_output_clipped * 255

    

    # #ADAM opt
    # beta1 =theano.shared(np.cast[theano.config.floatX](0.9), name='beta1')
    # beta2 =theano.shared(np.cast[theano.config.floatX](0.999), name='beta2')
    # eps =theano.shared(np.cast[theano.config.floatX](1e-8), name='eps')

    # updates = []
    # for param in params:
    #     m = theano.shared(param.get_value()*np.cast[theano.config.floatX](0.))    
    #     v = theano.shared(param.get_value()*np.cast[theano.config.floatX](0.))    
    #     new_m = beta1 * m + (np.cast[theano.config.floatX](1.) - beta1) * T.grad(cost, param)
    #     new_v = beta2 * v + (np.cast[theano.config.floatX](1.) - beta2) * T.sqr(T.grad(cost, param))
    #     updates.append((m, new_m))
    #     updates.append((v, new_v))
    #     updates.append((param, param - learning_rate*new_m/(T.sqrt(new_v) + eps)))

    #RMSProp
    # updates = []

    # for param in params:
    #     cache = theano.shared(param.get_value()*np.cast[theano.config.floatX](0.))    
    #     rms_decay = np.cast[theano.config.floatX](0.999)
    #     eps =theano.shared(np.cast[theano.config.floatX](1e-6)) 
    #     clip_grad = T.grad(cost,param)
 
    #     clip_grad = T.clip(clip_grad,-1.0,1.0)
    #     new_cache = rms_decay * cache + (np.cast[theano.config.floatX](1.0) - rms_decay) * clip_grad**2
    #     updates.append((cache, new_cache))
    #     updates.append((param,param - (learning_rate * clip_grad)/(T.sqrt(new_cache) + eps)))

    #nesterov momentum
    # updates = []
    # mu = np.cast[theano.config.floatX](.9)
    # for param in params:
    #     v_prev = theano.shared(param.get_value()*np.cast[theano.config.floatX](0.))    
    #     v = theano.shared(param.get_value()*np.cast[theano.config.floatX](0.))   
    #     clip_grad = T.grad(cost,param)
    #     clip_grad = T.clip(clip_grad,-1.0,1.0)
    
    #     new_v_prev = v
    #     new_v = mu * v - learning_rate * clip_grad

    #     updates.append((v_prev, new_v_prev))
    #     updates.append((v, new_v))
    #     updates.append((param,param - mu * new_v_prev + (np.cast[theano.config.floatX](1.0) + mu) * new_v))


    # #SGD
    clip_thresh = 1.0
    early_params = conv1.params + conv2.params
    for param in early_params:
        clip_grad = T.grad(cost,param)
        clip_grad = T.clip(clip_grad,-1.0,1.0)

        updates = [
            (param, param - 1e-4 * clip_grad)
        ]

    clip_thresh = 1.0
    for param in conv3.params:
        clip_grad = T.grad(cost,param)
        clip_grad = T.clip(clip_grad,-1.0,1.0)
        updates = [
            (param, param - 1e-5 * clip_grad)
        ]
    
    #Theano function complilation
    #if neccessary, could load here
    test_model = theano.function(
        [index],
        [cost,MSE_per_pixel,psnr,reconstucted_imgs],
        givens={
            x: test_set_x[index * batch_size: (index + 1) * batch_size],
            y: test_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )

    validate_model = theano.function(
        [index],
        [cost,MSE_per_pixel,psnr,reconstucted_imgs],
        givens={
            x: valid_set_x[index * batch_size: (index + 1) * batch_size],
            y: valid_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )

    train_model = theano.function(
        [index],
        [cost,MSE_per_pixel,psnr,reconstucted_imgs],
        updates=updates,
        givens={
            y: train_set_y[index * batch_size: (index + 1) * batch_size],
            x: train_set_x[index * batch_size: (index + 1) * batch_size]
        })

    decay_learning_rate_function = theano.function([],learning_rate,updates = [(learning_rate,learning_rate * 1)])

    train_nn(train_model, validate_model, test_model,
            n_train_batches, n_valid_batches, n_test_batches, n_epochs,output_len,decay_learning_rate_function,
            verbose = False)

    test_losses = []
    test_reconstructed = []
    test_pnsr = []
    test_MSE = []
    for i in xrange(n_test_batches):
                        test_output = test_model(i)                    
                        test_losses.append(test_output[0])
                        test_MSE.append(test_output[1])
                        test_pnsr.append(test_output[2])
                        test_reconstructed.append(test_output[3])


    return train_model,validate_model,test_model

def train_BN_SRCNN(train_set_x,train_set_y,valid_set_x,valid_set_y,test_set_x,test_set_y,
    n_train_batches, n_valid_batches, n_test_batches, n_epochs, batch_size,lr,l2=0,upsampling_factor=4):
    #Assume x to be shape (batch_size,3,33,33)
    x = T.matrix('x')
    y = T.matrix('y')

    theano.config.optimizer = 'fast_compile'
    print "theano optimizer: " + str(theano.config.optimizer)

    rng = np.random.RandomState(11111)
    index = T.lscalar() 

    reshaped_input = x.reshape((batch_size,3,33,33)) / 255
    reshaped_gt = y.reshape((batch_size,3,33,33)) / 255

    learning_rate = theano.shared(np.cast[theano.config.floatX](lr))
    
    #Filter params
    f1 = 9
    f2 = 1
    f3 = 5
    output_len = 33 - f1 - f2 - f3 + 3
    #Conv for Patch extraction
    conv1 = Conv_Layer_BN_ReLu(rng, reshaped_input, image_shape=(batch_size,3,33,33),filter_shape = (64,3,f1,f1))
    conv1_len = 33 - f1 + 1 
    #Conv for Non linear mapping

    conv2 = Conv_Layer_BN_ReLu(rng, conv1.output, image_shape=(batch_size,64,conv1_len,conv1_len),filter_shape = (32,64,f2,f2))
    conv2_len = conv1_len - f2 + 1
    #Conv for Reconstruction
    conv3 = Conv_Layer_None(rng, conv2.output, image_shape=(batch_size,32,conv2_len,conv2_len),filter_shape = (3,32,f3,f3))
    model_output = conv3.output

    params = conv3.params + conv2.params + conv1.params

    #grab center pixels
    center_start = (33 - output_len) / 2
    center_end = 33 - center_start
    sub_y = reshaped_gt[:,:,center_start:center_end,center_start:center_end]

    #MSE between center pixels of prediction and ground truth
    cost = 1.0/batch_size * T.sum((sub_y-model_output) ** 2) 

    regularization = 0
    for param in params:
        regularization += T.sum(param[0] ** 2)

    #PSNR of a patch is based on color space
    MSE_per_pixel = cost/(output_len*output_len*3) 
    psnr = 20 * T.log10(1) - 10 * T.log10(MSE_per_pixel)
    reconstucted_imgs = model_output
    cost += l2 * regularization

    updates = []

    for param in params:
        cache = theano.shared(param.get_value()*np.cast[theano.config.floatX](0.))    
        rms_decay = np.cast[theano.config.floatX](0.999)
        eps =theano.shared(np.cast[theano.config.floatX](1e-6)) 
        clip_grad = T.grad(cost,param)
 
        clip_grad = T.clip(clip_grad,-1.0,1.0)
        new_cache = rms_decay * cache + (np.cast[theano.config.floatX](1.0) - rms_decay) * clip_grad**2
        updates.append((cache, new_cache))
        updates.append((param,param - (learning_rate * clip_grad)/(T.sqrt(new_cache) + eps)))

    #Theano function complilation
    #if neccessary, could load here
    test_model = theano.function(
        [index],
        [cost,MSE_per_pixel,psnr,reconstucted_imgs],
        givens={
            x: test_set_x[index * batch_size: (index + 1) * batch_size],
            y: test_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )

    validate_model = theano.function(
        [index],
        [cost,MSE_per_pixel,psnr,reconstucted_imgs],
        givens={
            x: valid_set_x[index * batch_size: (index + 1) * batch_size],
            y: valid_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )

    train_model = theano.function(
        [index],
        [cost,MSE_per_pixel,psnr,reconstucted_imgs],
        updates=updates,
        givens={
            y: train_set_y[index * batch_size: (index + 1) * batch_size],
            x: train_set_x[index * batch_size: (index + 1) * batch_size]
        })

    decay_learning_rate_function = theano.function([],learning_rate,updates = [(learning_rate,learning_rate * 1)])

    train_nn(train_model, validate_model, test_model,
            n_train_batches, n_valid_batches, n_test_batches, n_epochs,output_len,decay_learning_rate_function,
            verbose = False)

    return train_model,validate_model,test_model

def load_dataset(dirname,data_type = 'data_x'):
    
    up_dir = os.path.dirname(os.getcwd())
    data_dir = os.path.join(up_dir,dirname)
    print data_dir

    if not os.path.isfile(data_dir+'.npz'):
        print "creating npz file"
        dataset_size = len(os.listdir(data_dir))
        if data_type == 'data_x':
            data = np.zeros((dataset_size,3,8,8))
        else:
            data = np.zeros((dataset_size,3,33,33))
        for root, dirs, files in os.walk(data_dir, topdown=False):
            with open(data_dir + '_filenames.txt','w') as write_file:
                for counter,name in enumerate(sorted(files)):
                    #write name to file
                    write_file.write(name + '\n')
                    full_filename = os.path.join(root, name)
                    img = scipy.ndimage.imread(full_filename) #(8,8,3)
                    img = np.transpose(img,(2,0,1))
                    data[counter,:,:,:] = img

        np.savez(data_dir + '.npz',data=data)
    else:
        print "loading from npz"
        data = np.load(data_dir + '.npz')['data']
    return data

def rebuild_images(reconstructed_patches,subimages_folder,patch_dim=21,dataset='train'):
    mapping = np.load(subimages_folder + 'mapping.npy')
    #mapping = np.load('/home/jon/Documents/Neural_Networks/project/SRCNN_Theano/Data/Validation_Subsamples_RGB_4mapping.npy')
    filenames = []
    shapes = []
    output_dir = 'recon_imgs' + "_" + dataset

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    shapesfilename = subimages_folder +'shapes.txt'
    #shapesfilename = '/home/jon/Documents/Neural_Networks/project/SRCNN_Theano/Data/Validation_Subsamples_RGB_4shapes.txt'
    with open(shapesfilename,'r') as namefile:
        for line in namefile:
            name = line.split('\t')[0].strip()
            shape = line.split('\t')[1].strip()
            filenames.append(name)
            shapes.append(shape)

    #recon patches is batch,depth,width,height
    past_img = mapping[0]
    img_counter = 0
    last_start = 0
    index = 0

    for i in xrange(len(filenames)):
        current_img = mapping[i]
        shape_str = shapes[i].replace("(","").split(",")

        img_width = int(shape_str[0]) 
        img_height = int(shape_str[1])
        max_w = int((img_width-33)/14) + 1
        max_h = int((img_height-33)/14) + 1

        #print orig_img_width,orig_img_height,orig_max_w,orig_max_h
        new_img_width = patch_dim+14*(max_w-1)
        new_img_height = patch_dim+14*(max_h-1)
        new_max_h = int((new_img_height-patch_dim)/14) + 1

        data = np.zeros((new_img_width,new_img_height,3))
        placements = np.zeros((new_img_width,new_img_height,3))
        # wait = input('here')
        for w in xrange(max_w): #what'st he correct w max? 
            for h in xrange(max_h):  
                index = last_start+(h+(new_max_h*w))
                patch = reconstructed_patches[index,:,:,:]

                w_beg = 14*w
                w_end = 14*w + patch_dim 
                # if w_end > img_width:
                #     w_end = img_width
                h_beg = 14*h
                h_end = 14*h + patch_dim
                # if h_end > img_height:
                #     h_end = img_height

                placements[w_beg:w_end,h_beg:h_end,:] += np.ones((patch_dim,patch_dim,3))

                data[w_beg:w_end,h_beg:h_end,:] += np.transpose(patch,(1,2,0))
        #average pixels
        data = data / placements
        scipy.misc.imsave(os.path.join(output_dir,filenames[i]), data)
        last_start = index + 1




###Debugging function
    # r_fun = theano.function([index],[index,reconstucted_imgs,cost],givens = {
    #         x: train_set_x[index * batch_size: (index + 1) * batch_size],
    #         y: train_set_y[index * batch_size: (index + 1) * batch_size]
    #         })
    # theano.printing.debugprint(r_fun(0))