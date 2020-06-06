# -*- coding: utf-8 -*-
"""IITB_Internship_Assignment3_Code.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/156ZmF9P-t4ZiOcD1TxAebLXvo9qFDjY_
"""

import pandas as pd
import codecs
import numpy as np
import xlrd
import re
import unicodedata
import tensorflow as tf
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.text import Tokenizer
import time
import os
from keras.models import Model
from keras.layers import Dense, Embedding, Activation, Permute
from keras.layers import Input, Flatten, Dropout
from keras.layers.recurrent import LSTM
from keras.layers.wrappers import TimeDistributed, Bidirectional

#Loading of Excel into a Pandas Dataframe and then further converting it into a Numpy Array

def load_dataset(file_path):
    #file_path = '/content/drive/My Drive/Colab Notebooks/Hi-En-Parallel_Corpus.xlsx'

    #Read Excel file using xlrd 
    book = xlrd.open_workbook(file_path, encoding_override='utf-8')
    #Convert Excel into Pandas Dataframe
    df = pd.read_excel(book)
    #Convert Pandas dataframe into Numpy Array
    dataset = np.array(df)
    return dataset

#Taking the Excel File Name from the user and displaying it as a Numpy Array

file_name = input("Enter the name of the Excel file containing mapping from Input Language to Target Language\n")
file_path = "/content/drive/My Drive/Colab Notebooks/" + str(file_name)
dataset = load_dataset(file_path)
print("The dataset after loading in Array is:")
print(dataset)

#Preprocessing the Dataset 
#1. Converting to lowercase
#2. Removing all the special characters
#3. Removing all numbers from text
#4. Adding Start and End Tags

def data_preprocessing(dataset):
    i=0
    for i in range(dataset.shape[0]):
        #Converting all sentences into lower case
        dataset[i,0] = str(dataset[i,0]).lower()
        dataset[i,1] = str(dataset[i,1]).lower()
        #Removing all special characters from the sentences
        temp = dataset[i,0]
        dataset[i,0] = ""
        for k in temp:
            dataset[i,0] += re.sub(r"[^a-zA-Z0-9]+", ' ', k)
        #Removing all numbers from the sentence
        dataset[i,0] = re.sub(r'\d+', '', dataset[i,0])
        dataset[i,1] = re.sub(r'\d+', '', dataset[i,1])
        #Attaching Start and End Tags
        dataset[i,0] = "<start> " + dataset[i,0] + " <end>"
        dataset[i,1] = "<start> " + dataset[i,1] + " <end>"
        #Eliminating extra spaces from tokens
        dataset[i,0] = re.sub(' +', ' ',dataset[i,0])
        dataset[i,1] = re.sub(' +', ' ',dataset[i,1]) 
        #dataset[i,0] = str(dataset[i,0].encode('utf-8'))
        #dataset[i,1] = str(dataset[i,1].encode('utf-8'))
    return dataset

#Implementing Preprocessing on the Dataset

dataset = data_preprocessing(dataset)
print("The dataset after data preprocessing:")
print(dataset)

#Splitting the Input and Target Language Statements from the Database

def input_target_split(dataset):
    #Store first column of Dataset as Input Language
    input_lang = dataset[:,0]
    #Store second column of Dataset as Target Language
    target_lang = dataset[:,1]
    return input_lang, target_lang

#Implementing the split on the Dataset

input_lang, target_lang = input_target_split(dataset)
print("The input language of dataset is:")
print(input_lang)
print("\n")
print("The target language of dataset is:")
print(target_lang)

#Initializing the Tokenizer along with padding

def initialize_tokenizer(lang):
    #Initialize Tokenizer
    lang_tokenizer = Tokenizer(filters='')
    #Fit the Tokenizer on the text
    lang_tokenizer.fit_on_texts(lang)
    #Convert the sentences into sequence of corresponding indices
    tensor = lang_tokenizer.texts_to_sequences(lang)
    #Pad the senquences to make them of equal length
    max_sequence_len = max([len(x) for x in tensor])
    tensor = tf.keras.preprocessing.sequence.pad_sequences(tensor, maxlen = max_sequence_len, padding='post')
    return tensor, lang_tokenizer

#Tokenizing the statements using the initialized tokenizer

def tokenize(input_lang, target_lang):
    #Tokenize the input language
    input_tensor, inp_lang_tokenizer = initialize_tokenizer(input_lang)
    #Tokenize the target language
    target_tensor, targ_lang_tokenizer = initialize_tokenizer(target_lang)
    return input_tensor, target_tensor, inp_lang_tokenizer, targ_lang_tokenizer

#Tokenize the input and target languages
input_tensor, target_tensor, inp_lang, targ_lang = tokenize(input_lang, target_lang)
#Split the dataset into train and set
input_tensor_train, input_tensor_val, target_tensor_train, target_tensor_val = train_test_split(input_tensor, target_tensor, test_size=0.2)

#Mapping of the Tokenized words to their Indices

def convert(lang, tensor):
    for t in tensor:
        if t!=0:
           print ("%d ----> %s" % (t, lang.index_word[t]))

#Displaying the Tokenized words and Word Indices mappings

print ("Input Language; index to word mapping")
convert(inp_lang, input_tensor_train[0])
print ("\n")
print ("Target Language; index to word mapping")
convert(targ_lang, target_tensor_train[0])

#Initializing necessary utilities for model building and training

input_word_to_index = inp_lang.word_index
target_word_to_index = targ_lang.word_index
input_index_to_word = dict([(value, key) for key, value in inp_lang.word_index.items()])
target_index_to_word = dict([(value, key) for key, value in targ_lang.word_index.items()])
max_len_input = (input_tensor.shape[1])
max_len_target = (target_tensor.shape[1])
input_vocab_size = len(inp_lang.word_index)
target_vocab_size = len(targ_lang.word_index)
rnn_cell_size = 128

#Initializing necessary utilities for model building and training

BUFFER_SIZE = len(input_tensor_train)
BATCH_SIZE = 64
steps_per_epoch = len(input_tensor_train)//BATCH_SIZE
embedding_dim = 256
units = 1024
vocab_inp_size = len(inp_lang.word_index)+1
vocab_tar_size = len(targ_lang.word_index)+1

dataset = tf.data.Dataset.from_tensor_slices((input_tensor_train, target_tensor_train)).shuffle(BUFFER_SIZE)
dataset = dataset.batch(BATCH_SIZE, drop_remainder=True)

#Initializaing Sample Batches to Display their Shapes

example_input_batch, example_target_batch = next(iter(dataset))
example_input_batch.shape, example_target_batch.shape

#Building the Encoder Class for the Attention Model of RNN

class Encoder(tf.keras.Model):
  def __init__(self, vocab_size, embedding_dim, enc_units, batch_sz):
    super(Encoder, self).__init__()
    self.batch_sz = batch_sz
    self.enc_units = enc_units
    self.embedding = tf.keras.layers.Embedding(vocab_size, embedding_dim)
    self.gru = tf.keras.layers.GRU(self.enc_units,
                                   return_sequences=True,
                                   return_state=True,
                                   recurrent_initializer='glorot_uniform')

  def call(self, x, hidden):
    x = self.embedding(x)
    output, state = self.gru(x, initial_state = hidden)
    return output, state

  def initialize_hidden_state(self):
    return tf.zeros((self.batch_sz, self.enc_units))

#Assigning the Encoder class with an object

encoder = Encoder(vocab_inp_size, embedding_dim, units, BATCH_SIZE)

# sample input
sample_hidden = encoder.initialize_hidden_state()
sample_output, sample_hidden = encoder(example_input_batch, sample_hidden)
print ('Encoder output shape: (batch size, sequence length, units) {}'.format(sample_output.shape))
print ('Encoder Hidden state shape: (batch size, units) {}'.format(sample_hidden.shape))

#Building the Bahdanau Attention Layer Class for the Attention Model of RNN

class BahdanauAttention(tf.keras.layers.Layer):
  def __init__(self, units):
    super(BahdanauAttention, self).__init__()
    self.W1 = tf.keras.layers.Dense(units)
    self.W2 = tf.keras.layers.Dense(units)
    self.V = tf.keras.layers.Dense(1)

  def call(self, query, values):
    # query hidden state shape == (batch_size, hidden size)
    # query_with_time_axis shape == (batch_size, 1, hidden size)
    # values shape == (batch_size, max_len, hidden size)
    # we are doing this to broadcast addition along the time axis to calculate the score
    query_with_time_axis = tf.expand_dims(query, 1)

    # score shape == (batch_size, max_length, 1)
    # we get 1 at the last axis because we are applying score to self.V
    # the shape of the tensor before applying self.V is (batch_size, max_length, units)
    score = self.V(tf.nn.tanh(
        self.W1(query_with_time_axis) + self.W2(values)))

    # attention_weights shape == (batch_size, max_length, 1)
    attention_weights = tf.nn.softmax(score, axis=1)

    # context_vector shape after sum == (batch_size, hidden_size)
    context_vector = attention_weights * values
    context_vector = tf.reduce_sum(context_vector, axis=1)

    return context_vector, attention_weights

#Assigning the Bahdanau Attention Layer class with an object

attention_layer = BahdanauAttention(10)
attention_result, attention_weights = attention_layer(sample_hidden, sample_output)

print("Attention result shape: (batch size, units) {}".format(attention_result.shape))
print("Attention weights shape: (batch_size, sequence_length, 1) {}".format(attention_weights.shape))

#Building the Decoder Class for the Attention Model of RNN

class Decoder(tf.keras.Model):
  def __init__(self, vocab_size, embedding_dim, dec_units, batch_sz):
    super(Decoder, self).__init__()
    self.batch_sz = batch_sz
    self.dec_units = dec_units
    self.embedding = tf.keras.layers.Embedding(vocab_size, embedding_dim)
    self.gru = tf.keras.layers.GRU(self.dec_units,
                                   return_sequences=True,
                                   return_state=True,
                                   recurrent_initializer='glorot_uniform')
    self.fc = tf.keras.layers.Dense(vocab_size)

    # used for attention
    self.attention = BahdanauAttention(self.dec_units)

  def call(self, x, hidden, enc_output):
    # enc_output shape == (batch_size, max_length, hidden_size)
    context_vector, attention_weights = self.attention(hidden, enc_output)

    # x shape after passing through embedding == (batch_size, 1, embedding_dim)
    x = self.embedding(x)

    # x shape after concatenation == (batch_size, 1, embedding_dim + hidden_size)
    x = tf.concat([tf.expand_dims(context_vector, 1), x], axis=-1)

    # passing the concatenated vector to the GRU
    output, state = self.gru(x)

    # output shape == (batch_size * 1, hidden_size)
    output = tf.reshape(output, (-1, output.shape[2]))

    # output shape == (batch_size, vocab)
    x = self.fc(output)

    return x, state, attention_weights

#Assigning the Decoder class with an object

decoder = Decoder(vocab_tar_size, embedding_dim, units, BATCH_SIZE)

sample_decoder_output, _, _ = decoder(tf.random.uniform((BATCH_SIZE, 1)),
                                      sample_hidden, sample_output)

print ('Decoder output shape: (batch_size, vocab size) {}'.format(sample_decoder_output.shape))

#Initializing the Optimizer and Loss Function for the Model Training

optimizer = tf.keras.optimizers.Adam()
loss_object = tf.keras.losses.SparseCategoricalCrossentropy(
    from_logits=True, reduction='none')

def loss_function(real, pred):
  mask = tf.math.logical_not(tf.math.equal(real, 0))
  loss_ = loss_object(real, pred)

  mask = tf.cast(mask, dtype=loss_.dtype)
  loss_ *= mask

  return tf.reduce_mean(loss_)

#Initializing the checkpoints in case the the training needs to be continued in future

checkpoint_dir = './training_checkpoints'
checkpoint_prefix = os.path.join(checkpoint_dir, "ckpt")
checkpoint = tf.train.Checkpoint(optimizer=optimizer,
                                 encoder=encoder,
                                 decoder=decoder)

#Performing the training on the Model on one Epoch

@tf.function
def train_step(inp, targ, enc_hidden):
  loss = 0

  with tf.GradientTape() as tape:
    enc_output, enc_hidden = encoder(inp, enc_hidden)

    dec_hidden = enc_hidden

    dec_input = tf.expand_dims([targ_lang.word_index['<start>']] * BATCH_SIZE, 1)

    # Teacher forcing - feeding the target as the next input
    for t in range(1, targ.shape[1]):
      # passing enc_output to the decoder
      predictions, dec_hidden, _ = decoder(dec_input, dec_hidden, enc_output)

      loss += loss_function(targ[:, t], predictions)

      # using teacher forcing
      dec_input = tf.expand_dims(targ[:, t], 1)

  batch_loss = (loss / int(targ.shape[1]))

  variables = encoder.trainable_variables + decoder.trainable_variables

  gradients = tape.gradient(loss, variables)

  optimizer.apply_gradients(zip(gradients, variables))

  return batch_loss

#The Model training with defining the No. of Epochs the Inputs and Labels

EPOCHS = 10

for epoch in range(EPOCHS):
  start = time.time()

  enc_hidden = encoder.initialize_hidden_state()
  total_loss = 0

  for (batch, (inp, targ)) in enumerate(dataset.take(steps_per_epoch)):
    batch_loss = train_step(inp, targ, enc_hidden)
    total_loss += batch_loss

    if batch % 100 == 0:
      print('Epoch {} Batch {} Loss {:.4f}'.format(epoch + 1,
                                                   batch,
                                                   batch_loss.numpy()))
  # saving (checkpoint) the model every 2 epochs
  if (epoch + 1) % 2 == 0:
    checkpoint.save(file_prefix = checkpoint_prefix)

  print('Epoch {} Loss {:.4f}'.format(epoch + 1,
                                      total_loss / steps_per_epoch))
  print('Time taken for 1 epoch {} sec\n'.format(time.time() - start))

#Evaluating the Trained Model over Test Sentence

def evaluate(sentence):
  attention_plot = np.zeros((max_length_targ, max_length_inp))

  sentence = preprocess_sentence(sentence)

  inputs = [inp_lang.word_index[i] for i in sentence.split(' ')]
  inputs = tf.keras.preprocessing.sequence.pad_sequences([inputs],
                                                         maxlen=max_length_inp,
                                                         padding='post')
  inputs = tf.convert_to_tensor(inputs)

  result = ''

  hidden = [tf.zeros((1, units))]
  enc_out, enc_hidden = encoder(inputs, hidden)

  dec_hidden = enc_hidden
  dec_input = tf.expand_dims([targ_lang.word_index['<start>']], 0)

  for t in range(max_length_targ):
    predictions, dec_hidden, attention_weights = decoder(dec_input,
                                                         dec_hidden,
                                                         enc_out)

    # storing the attention weights to plot later on
    attention_weights = tf.reshape(attention_weights, (-1, ))
    attention_plot[t] = attention_weights.numpy()

    predicted_id = tf.argmax(predictions[0]).numpy()

    result += targ_lang.index_word[predicted_id] + ' '

    if targ_lang.index_word[predicted_id] == '<end>':
      return result, sentence, attention_plot

    # the predicted ID is fed back into the model
    dec_input = tf.expand_dims([predicted_id], 0)

  return result, sentence, attention_plot

#Function for plotting the attention weights

def plot_attention(attention, sentence, predicted_sentence):
  fig = plt.figure(figsize=(10,10))
  ax = fig.add_subplot(1, 1, 1)
  ax.matshow(attention, cmap='viridis')

  fontdict = {'fontsize': 14}

  ax.set_xticklabels([''] + sentence, fontdict=fontdict, rotation=90)
  ax.set_yticklabels([''] + predicted_sentence, fontdict=fontdict)

  ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
  ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

  plt.show()

#Translating the sentence from Input Language to Target Language

def translate(sentence):
  result, sentence, attention_plot = evaluate(sentence)

  print('Input: %s' % (sentence))
  print('Predicted translation: {}'.format(result))

  attention_plot = attention_plot[:len(result.split(' ')), :len(sentence.split(' '))]
  plot_attention(attention_plot, sentence.split(' '), result.split(' '))

#Restoring the latest checkpoint in checkpoint_dir
checkpoint.restore(tf.train.latest_checkpoint(checkpoint_dir))

#Translating the statement giving the statement in the input language

translate('I love to play football.')

#Computing the Bleu Score by Comparing the Statement Translated by the Model and Human/Provided Translation

from nltk.translate.bleu_score import sentence_bleu
from nltk.tokenize import word_tokenize
reference = [word_tokenize(translate(input_lang[100]))]
candidate = word_tokenize(target_lang[100])
score = sentence_bleu(reference, candidate)
print(score)