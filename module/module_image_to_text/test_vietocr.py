from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg
from PIL import Image

config = Cfg.load_config_from_name('vgg_seq2seq')
config['cnn']['pretrained'] = False
config['device'] = 'cpu'
detector = Predictor(config)

img = Image.open('test_out/frame_240_minsize_crop_0.jpg')
text = detector.predict(img)
print("Recognized text:", text)
