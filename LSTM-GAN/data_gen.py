import numpy as np
from keras.preprocessing.text import Tokenizer

from enums import NoiseMode, Conf, WordEmbedding
from io_helper import load_pickle_file
from list_helpers import print_progress


def to_categorical_lists(captions, config):
	matrix = np.zeros((len(captions), config[Conf.MAX_SEQ_LENGTH], config[Conf.VOCAB_SIZE]))
	for caption_index in range(len(captions)):
		caption = captions[caption_index]
		for word_index in range(config[Conf.MAX_SEQ_LENGTH]):
			if word_index >= len(caption):
				word = 0
			else:
				word = caption[word_index]
			matrix[caption_index, word_index, word] = 1.
	return matrix


def onehot_to_softmax(one_hot, max_range=(0.5, 1.0), min_range=(0.0, 0.001)):
	softmax = np.random.uniform(min_range[0], min_range[1], one_hot.shape).astype(dtype="float32")
	for i, one_hot_sentence in enumerate(one_hot):
		for j, one_hot_word in enumerate(one_hot_sentence):
			new_word = softmax[i][j]
			new_word[np.argmax(one_hot_word)] = np.random.uniform(max_range[0], max_range[1])
			word_sum = new_word.sum()
			softmax[i][j] = new_word / word_sum
	return softmax


def conditional_onehot_to_softmax(one_hot_sentences, predictions):
	softmax = np.random.uniform(min_range[0], min_range[1], one_hot_sentences.shape).astype(dtype="float32")
	for i, one_hot_sentence in enumerate(one_hot_sentences):
		for j, one_hot_word in enumerate(one_hot_sentence):
			new_word = softmax[i][j]
			new_word[np.argmax(one_hot_word)] = np.random.uniform(max_range[0], max_range[1])
			word_sum = new_word.sum()
			softmax[i][j] = new_word / word_sum
	return softmax


def generate_index_captions(config, cap_data=-1):
	max_seq_length = config[Conf.MAX_SEQ_LENGTH]
	nb_words = config[Conf.VOCAB_SIZE]
	path = "dataset/Flickr30k.txt"

	sentence_file = open(path)
	if cap_data == -1:
		word_captions = sentence_file.readlines()
	else:
		word_captions = sentence_file.readlines()[:cap_data]
	sentence_file.close()

	word_captions = [(line.split("\t")[1]).strip() for line in word_captions]
	word_captions = ['<SOS> ' + line + ' <EOS>' for line in word_captions]

	tokenizer = Tokenizer(nb_words=nb_words, filters="""!"#$%&'()*+-/:;=?@[\]^_`{|}~""")
	tokenizer.fit_on_texts(word_captions)
	index_captions = tokenizer.texts_to_sequences(word_captions)
	index_captions = [cap for cap in index_captions if len(cap) <= max_seq_length]

	word_to_id_dict = tokenizer.word_index
	id_to_word_dict = {token: idx for idx, token in word_to_id_dict.items()}

	return index_captions, id_to_word_dict, word_to_id_dict


def get_flickr_sentences(cap_data):
	path = "dataset/Flickr30k.txt"
	sentence_file = open(path)
	if cap_data == -1:
		word_captions = sentence_file.readlines()
	else:
		word_captions = sentence_file.readlines()[:cap_data]
	sentence_file.close()
	word_captions = [(line.split("\t")[1]).strip() for line in word_captions]
	return word_captions


np_noise = None


def generate_input_noise(config):
	if config[Conf.NOISE_MODE] == NoiseMode.REPEAT:
		noise_matrix = np.zeros(
			(config[Conf.BATCH_SIZE], config[Conf.MAX_SEQ_LENGTH], config[Conf.NOISE_SIZE]))
		for batch_index in range(config[Conf.BATCH_SIZE]):
			word_noise = np.random.uniform(-1, 1, config[Conf.NOISE_SIZE])
			for word_index in range(config[Conf.MAX_SEQ_LENGTH]):
				noise_matrix[batch_index][word_index] = word_noise

		return noise_matrix

	elif config[Conf.NOISE_MODE] == NoiseMode.NEW:
		return np.random.rand(config[Conf.BATCH_SIZE], config[Conf.MAX_SEQ_LENGTH], config[Conf.NOISE_SIZE])

	elif config[Conf.NOISE_MODE] == NoiseMode.FIRST_ONLY:
		noise_matrix = np.zeros((config[Conf.BATCH_SIZE], config[Conf.MAX_SEQ_LENGTH], config[Conf.NOISE_SIZE]))
		for batch_index in range(config[Conf.BATCH_SIZE]):
			word_noise = np.random.uniform(0, 1, config[Conf.NOISE_SIZE])
			noise_matrix[batch_index][0] = word_noise
		return noise_matrix

	elif config[Conf.NOISE_MODE] == NoiseMode.ONES:
		return np.ones((config[Conf.BATCH_SIZE], config[Conf.MAX_SEQ_LENGTH], config[Conf.NOISE_SIZE]))

	elif config[Conf.NOISE_MODE] == NoiseMode.ENCODING:
		global np_noise
		if np_noise is None:
			np_noise = load_pickle_file("pred.pkl")[:1]
		return np_noise


def get_word_embeddings():
	embeddings_index = {}
	f = open('dataset/glove.6B.300d.txt')
	count = 0
	for line in f:
		values = line.split()
		word = values[0]
		coefs = np.asarray(values[1:], dtype='float32')
		embeddings_index[word] = coefs
		count += 1
		if count % 100 == 0:
			print_progress(count, 400000, prefix="Producing glove word embeddings")
	f.close()
	return embeddings_index


def generate_embedding_captions(config):
	cap_data = config[Conf.DATASET_SIZE]
	print "Loading Flickr sentences..."
	sentences = get_flickr_sentences(cap_data)
	word_list_sentences = []
	for sentence in sentences:
		word_list = ["<sos>"]
		for word in sentence.split(" "):
			word_list.append(word.lower())
		word_list.append("<eos>")
		word_list_sentences.append(word_list)
	# word_list_sentences = [[word.lower() for word in sentence.split(" ")] for sentence in sentences]

	if config[Conf.WORD_EMBEDDING] == WordEmbedding.GLOVE:
		print "Loading Glove dictionary..."
		word_embedding_dict = get_word_embeddings()
	else:
		print "Loading Word2Vec dictionary (%s)..." % config[Conf.WORD_EMBEDDING]
		word_embedding_dict = load_pickle_file("%s" % config[Conf.WORD_EMBEDDING])
	return np.asarray(word_list_sentences), word_embedding_dict


def emb_get_training_batch(training_batch, word_embedding_dict, config):
	embedding_lists = []
	for word_list in training_batch:
		embedding_sentence = []
		for word_string in word_list:
			if word_string in word_embedding_dict:
				word_embedding = word_embedding_dict[word_string]
				embedding_sentence.append(word_embedding)
		if len(embedding_sentence) > config[Conf.MAX_SEQ_LENGTH]:
			embedding_sentence = embedding_sentence[:config[Conf.MAX_SEQ_LENGTH]]
		while len(embedding_sentence) < config[Conf.MAX_SEQ_LENGTH]:
			zeros = np.zeros(config[Conf.EMBEDDING_SIZE])
			embedding_sentence.insert(0, zeros)
		embedding_lists.append(embedding_sentence)
	return np.asarray(embedding_lists)


if __name__ == '__main__':
	word_list_sentences, word_embedding_dict = generate_embedding_captions()
# batch = word_list_sentences[:32]
# config = {
# 	Conf.MAX_SEQ_LENGTH: 10,
# 	Conf.EMBEDDING_SIZE: 300
# }
# embedding_lists = emb_get_training_batch(batch, word_embedding_dict, config)
# print embedding_lists.shape
