import qlib
from qlib.workflow import R
from qlib .utils import init_instance_by_config
import yaml 
#import jobpy
from pathlib import Path




def train_model(config_path: str, exp_name: str):
    #1. загружаем конфиг
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    #2 инит данных datahandler from data prep
    dataset = init_instance_by_config(config["dataset_config"])

    #3 инит модели на основе конфига
    model = init_instance_by_config(config["model_config"])
    
    #4 запуск рекорд
    with R.start(experiment_name=exp_name):
        print ("Training started...")
        model.fit(dataset)
        #сейв модели в кулибе
        R.save_objects(trained_model=model)

        #прогноз для дальнейшего бектеста

        print("Predicting...")
        pred_score = model.predict(dataset)

        # сохраняем прогноз
        R.save_objects(pred_score=pred_score)
        R.save_objects(label=dataset.prepare("test", col_set="label"))

        print(f"обучение завершено. прогноз сохранен в {R.get_recorder().get_local_dir()}")

    return model, pred_score

if __name__ == "__main__":
    CONFIG_PATH = "configs/workflow_config.yaml"

    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data")

    train_model(CONFIG_PATH)
                                    