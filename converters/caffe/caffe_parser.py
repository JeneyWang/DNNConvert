from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from converters.caffe.caffe_graph import CaffeGraph
import common.IR.graph_pb2 as graph_pb2
from common.IR.graph_pb2 import NodeDef, GraphDef, DataType
from common.DataStructure.parser import Parser

class CaffeParser(Parser):
   
    activation_map = {
            "ReLU"    : "Relu",
            'Dropout' : "Softmax",
            'sigmoid' : "Sigmoid",
            "tanh"    : "Tanh"
            }
    


    @staticmethod
    def _load_model(model_network_path, model_weight_path):
        """Load a caffe model from disk

        Parameters
        ----------
        model_network_path: str
            Path where the model network path is (protobuf file)

        model_weight_path: str
            Path where the model network weights are (hd5 file)

        Returns
        -------
        model: A caffe model
        """
        import converters.caffe.caffe_pb2 as caffe_pb2
        from common.utils import load_protobuf_from_file

        # Load the model network
        loaded_model = caffe_pb2.NetParameter()
        load_protobuf_from_file(loaded_model, model_network_path)

        # Load the model weights
        """
        loaded_model = model_from_json(loaded_model_json)
        if os.path.isfile(model_weight_path) == True:
            loaded_model.load_weights(model_weight_path)
        else:
            print("Warning: Caffe Model Weight File [%s] is not found." % (model_weight_path))
        """
        print ("Caffe model file [%s] loaded successfully." % model_network_path)
        return loaded_model



    @classmethod
    def __init__(self, model, phase):
        super(CaffeParser, self).__init__()
        
        # load model files into caffe graph
        model = CaffeParser._load_model(model[0], model[1])

        # Build network graph
        self.caffe_graph =  CaffeGraph(model, phase)
        self.caffe_graph.build()



    @classmethod
    def gen_IR(self):
        for layer in self.caffe_graph.topological_sort:
            current_node = self.caffe_graph.get_node(layer)
            node_type = current_node.type

            if hasattr(self, "rename_" + node_type):
                func = getattr(self, "rename_" + node_type)
                func(current_node)
            else:
                print("CaffeParser has not supported operator [%s]." % (node_type))
                self.rename_UNKNOWN(current_node)

        print (self.IR_graph)


    @staticmethod
    def _copy_and_reop(source_node, IR_node, new_op = None):
        node_info = source_node.layer
        if new_op == None:
            new_op = source_node.type
        IR_node.name = source_node.name
        IR_node.op = new_op
        if hasattr(node_info, "dtype"):
            pass



    @staticmethod
    def _convert_inedge(source_node, IR_node, layer_name_map):
        for e in source_node.in_edges:
            IR_node.input.append(layer_name_map[e])



    @staticmethod
    def _copy_shape(source_node, target_node):
        if hasattr(source_node, "output_shape"):
            for dim in source_node.output_shape:
                new_dim = target_node.attr["shape"].shape.dim.add()
                if dim == None:
                    new_dim.size = -1
                else:
                    new_dim.size = dim
        else:
            target_node.attr["shape"].shape.unknown_rank = True


    @staticmethod
    def _convert_dataformat(source_node, target_node):
        if source_node.keras_layer.data_format == 'channels_last':
            target_node.attr["data_format"].s = "NHWC"
        elif source_node.keras_layer.data_format == 'channels_first':
            target_node.attr["data_format"].s = "NCHW"
        else:
            print("Warning: [%s] don't have data format info." % (source_node.keras_layer.name))



    @staticmethod
    def _convert_padding(source_node, target_node):
        if source_node.keras_layer.padding == 'valid':
            target_node.attr["padding"].s = "VALID"
        elif source_node.keras_layer.padding == 'same':
            target_node.attr["padding"].s = "SAME"
        else:
            print ("Error: Invalid embedding [%s]!" % (source_node.keras_layer.padding))



    @classmethod
    def _defuse_activation(self, source_node):
        if source_node.activation == "":
            return
        
        IR_node = self.IR_graph.node.add()
        IR_node.name = keras_node.keras_layer.name + "_activation"
        IR_node.op = CaffeParser.activation_map[source_node.activation]
        IR_node.input.append(keras_node.keras_layer.name)
        self.keras_graph.layer_name_map[keras_node.keras_layer.name] = IR_node.name



    @classmethod
    def _convert_convolution(self, source_node, IR_node):
        # name, op
        CaffeParser._copy_and_reop(source_node, IR_node)

        # input edge
        CaffeParser._convert_inedge(source_node, IR_node, self.caffe_graph.layer_name_map)
        
        # padding        
#        Keras2Parser._convert_padding(keras_node, IR_node)

        """
        # filter
        for e in keras_node.keras_layer.kernel_size:
            IR_node.attr["filter"].list.i.append(e)

        if self.data_format == "channels_last":
            IR_node.attr["filter"].list.i.append(keras_node.keras_layer.input_shape[-1])
        else:
            IR_node.attr["filter"].list.i.append(keras_node.keras_layer.input_shape[1])
        IR_node.attr["filter"].list.i.append(keras_node.keras_layer.filters)
        """
        # use_bias
        IR_node.attr["use_bias"].b = source_node.layer.convolution_param.bias_term
        """
        # strides
        for e in keras_node.keras_layer.strides:
            IR_node.attr["strides"].list.i.append(e)

        while len(IR_node.attr["strides"].list.i) < dim:
            IR_node.attr["strides"].list.i.append(IR_node.attr["strides"].list.i.at(0))

        # activation
        self._defuse_activation(source_node)
        """


    @classmethod
    def _convert_padding_api(self, keras_node, IR_node, mode):
         # name, op
        Keras2Parser._copy_and_reop(keras_node, IR_node, "pad")

        # input edge
        Keras2Parser._convert_inedge(keras_node, IR_node, self.keras_graph.layer_name_map)
        
        IR_node.attr['mode'].s = mode

        # padding
        for e in keras_node.keras_layer.padding:
            for j in e:
                IR_node.attr["padding"].list.i.append(j)



    @classmethod
    def rename_UNKNOWN(self, source_node):
        # only for training
        IR_node = self.IR_graph.node.add()
        
        # name, op
        CaffeParser._copy_and_reop(source_node, IR_node)
        
        # input edge
        CaffeParser._convert_inedge(source_node, IR_node, self.caffe_graph.layer_name_map)


    @classmethod
    def rename_Data(self, source_node):
        self.rename_DataInput(source_node)


    @classmethod
    def rename_DataInput(self, source_node):
        # only for training
        IR_node = self.IR_graph.node.add()
        
        # name, op
        CaffeParser._copy_and_reop(source_node, IR_node, "DataInput")
        
        # shape
#        Keras2Parser._copy_shape(source_node.keras_layer, IR_node)



    @classmethod
    def rename_Conv1D(self, keras_node):
        IR_node = self.IR_graph.node.add()        
        self._convert_convolution(keras_node, IR_node, 1)



    @classmethod
    def rename_Convolution(self, source_node):
        IR_node = self.IR_graph.node.add() 
        self._convert_convolution(source_node, IR_node)



    @classmethod
    def rename_Conv3D(self, source_node):
        IR_node = self.IR_graph.node.add()         
        self._convert_convolution(keras_node, IR_node, 3)
       


    @classmethod
    def rename_GlobalMaxPooling1D(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node, "GlobalMaxPool1D")

        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)



    @classmethod
    def rename_GlobalAveragePooling2D(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node, "GlobalAvgPool2D")

        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)



    @classmethod
    def rename_MaxPooling2D(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node, "MaxPool2D")

        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)

        # padding
        Keras2Parser._convert_padding(source_node, IR_node)

        # strides
        if isinstance(source_node.keras_layer.strides, tuple) or isinstance(source_node.keras_layer.strides, list):
            sh, sw = source_node.keras_layer.strides
        else:
            sh = source_node.keras_layer.strides
            sw = sh

        IR_node.attr["strides"].list.i.append(1)
        IR_node.attr["strides"].list.i.append(sh)
        IR_node.attr["strides"].list.i.append(sw)
        IR_node.attr["strides"].list.i.append(1)

        # pool_size
        if isinstance(source_node.keras_layer.pool_size, tuple) or isinstance(source_node.keras_layer.pool_size, list):
            ph, pw = source_node.keras_layer.pool_size
        else:
            ph = source_node.keras_layer.pool_size
            pw = ph
    
        IR_node.attr["ksize"].list.i.append(1)
        IR_node.attr["ksize"].list.i.append(ph)
        IR_node.attr["ksize"].list.i.append(pw)
        IR_node.attr["ksize"].list.i.append(1)




    @classmethod
    def rename_Dropout(self, source_node):
        # only for training
        IR_node = self.IR_graph.node.add()

        # name, op
        CaffeParser._copy_and_reop(source_node, IR_node)

        # input edge
        CaffeParser._convert_inedge(source_node, IR_node, self.caffe_graph.layer_name_map)

        IR_node.attr["keep_prob"].f = source_node.layer.dropout_param.dropout_ratio
  

    @classmethod
    def rename_Dense(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node, "Fully_connected")
        
        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)

        # units
        IR_node.attr["units"].i = source_node.keras_layer.units

        # use_bias
        IR_node.attr["use_bias"].b = source_node.keras_layer.use_bias

        # activation
        self._defuse_activation(source_node)



    @classmethod
    def rename_Flatten(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node)

        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)



    @classmethod
    def rename_Activation(self, keras_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(keras_node, IR_node, self.activation_map[keras_node.keras_layer.activation.__name__])

        # input edge
        Keras2Parser._convert_inedge(keras_node, IR_node, self.keras_graph.layer_name_map)


    @classmethod
    def rename_ReLU(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        CaffeParser._copy_and_reop(source_node, IR_node, "Relu")

        # input edge
        CaffeParser._convert_inedge(source_node, IR_node, self.caffe_graph.layer_name_map)



    @classmethod
    def rename_Embedding(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node)
        
        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)

        # input_dim
        IR_node.attr["input_dim"].i = source_node.keras_layer.input_dim

        # output_dim
        IR_node.attr["output_dim"].i = source_node.keras_layer.output_dim

        # mask_zero
        IR_node.attr["mask_zero"].b = source_node.keras_layer.mask_zero



    @classmethod
    def rename_LSTM(self, keras_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(keras_node, IR_node)
        
        # input edge
        Keras2Parser._convert_inedge(keras_node, IR_node, self.keras_graph.layer_name_map)

        # units
        IR_node.attr["units"].i = keras_node.keras_layer.units

        # use_bias
        IR_node.attr["use_bias"].b = keras_node.keras_layer.use_bias

        # for Keras, drop_out and recurrent_dropout
        IR_node.attr["dropout"].f = keras_node.keras_layer.dropout
        IR_node.attr["recurrent_dropout"].f = keras_node.keras_layer.recurrent_dropout

        # activation
        self._defuse_activation(keras_node)



    @classmethod
    def rename_GRU(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node)
        
        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)

        # units
        IR_node.attr["units"].i = source_node.keras_layer.units

        # activation
        self._defuse_activation(source_node)



    @classmethod
    def rename_Add(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node)
        
        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)



    @classmethod
    def rename_Concatenate(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node, 'Concat')
        
        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)


    @classmethod
    def rename_Reshape(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node, 'Concat')
        
        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)

        # for target shape
        for e in source_node.keras_layer.target_shape:
            IR_node.attr["Tshape"].list.i.append(e)


    @classmethod
    def rename_Lambda(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node, "Keras Lambda")
        
        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)

        IR_node.attr['function'].s = source_node.keras_layer.function.__name__
        for dim in source_node.keras_layer.output_shape:
            new_dim = IR_node.attr["output_shape"].shape.dim.add()
            if dim == None:
                new_dim.size = -1
            else:
                new_dim.size = dim

        # arguments not implementent
        #print (type(source_node.keras_layer.arguments))



    @classmethod
    def rename_BatchNormalization(self, keras_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(keras_node, IR_node, 'BatchNorm')
        
        # input edge
        Keras2Parser._convert_inedge(keras_node, IR_node, self.keras_graph.layer_name_map)

        # axis
        IR_node.attr['axis'].i = keras_node.keras_layer.axis

        # scale
        IR_node.attr['scale'].b = keras_node.keras_layer.scale



    @classmethod
    def rename_ZeroPadding2D(self, keras_node):
        IR_node = self.IR_graph.node.add()
        self._convert_padding_api(keras_node, IR_node, "CONSTANT")



    @classmethod
    def rename_AveragePooling2D(self, source_node):
        IR_node = self.IR_graph.node.add()

        # name, op
        Keras2Parser._copy_and_reop(source_node, IR_node, "AvgPool2D")

        # input edge
        Keras2Parser._convert_inedge(source_node, IR_node, self.keras_graph.layer_name_map)

        # padding
        Keras2Parser._convert_padding(source_node, IR_node)

        # strides
        if isinstance(source_node.keras_layer.strides, tuple) or isinstance(source_node.keras_layer.strides, list):
            sh, sw = source_node.keras_layer.strides
        else:
            sh = source_node.keras_layer.strides
            sw = sh

        IR_node.attr["strides"].list.i.append(1)
        IR_node.attr["strides"].list.i.append(sh)
        IR_node.attr["strides"].list.i.append(sw)
        IR_node.attr["strides"].list.i.append(1)

        # pool_size
        if isinstance(source_node.keras_layer.pool_size, tuple) or isinstance(source_node.keras_layer.pool_size, list):
            ph, pw = source_node.keras_layer.pool_size
        else:
            ph = source_node.keras_layer.pool_size
            pw = ph
    
        IR_node.attr["ksize"].list.i.append(1)
        IR_node.attr["ksize"].list.i.append(ph)
        IR_node.attr["ksize"].list.i.append(pw)
        IR_node.attr["ksize"].list.i.append(1)
