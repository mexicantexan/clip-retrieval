import os

os.environ["CUDA_VISIBLE_DEVICES"] = ""

from img2dataset import download
from clip_retrieval import clip_inference
from clip_retrieval import clip_index
import pandas as pd
import shutil
import subprocess
import time
import requests
import logging


LOGGER = logging.getLogger(__name__)

test_list = [
    ["first", "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg"],
    ["second", "https://upload.wikimedia.org/wikipedia/commons/d/d4/Cat_March_2010-1a.jpg"],
    [
        "third",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Baby_cat_turning.jpg/800px-Baby_cat_turning.jpg",
    ],
    ["fourth", "https://upload.wikimedia.org/wikipedia/commons/5/51/Boscoe2_%288571299519%29.jpg"],
    [
        "fifth",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/Cat_004_%286098630659%29.jpg/1280px-Cat_004_%286098630659%29.jpg",
    ],
    [None, "https://upload.wikimedia.org/wikipedia/commons/e/e1/Cats_144_%287179618326%29.jpg"],
]


def generate_parquet(output_file):
    df = pd.DataFrame(test_list, columns=["caption", "url"])
    df.to_parquet(output_file)


def test_end2end():
    current_folder = os.path.dirname(__file__)
    test_folder = current_folder + "/" + "test_folder"
    if os.path.exists(test_folder):
        shutil.rmtree(test_folder)
    if not os.path.exists(test_folder):
        os.mkdir(test_folder)
    url_list_name = os.path.join(test_folder, "url_list")
    image_folder_name = os.path.join(test_folder, "images")

    url_list_name += ".parquet"
    generate_parquet(url_list_name)

    download(
        url_list_name,
        image_size=256,
        output_folder=image_folder_name,
        thread_count=32,
        input_format="parquet",
        output_format="webdataset",
        url_col="url",
        caption_col="caption",
    )

    assert os.path.exists(image_folder_name)

    embeddings_folder = os.path.join(test_folder, "embeddings")

    clip_inference(
        input_dataset=f"{image_folder_name}/00000.tar",
        output_folder=embeddings_folder,
        input_format="webdataset",
        enable_metadata=True,
        write_batch_size=100000,
        batch_size=8,
        cache_path=None,
    )

    assert os.path.exists(embeddings_folder)

    index_folder = os.path.join(test_folder, "index")

    os.mkdir(index_folder)

    clip_index(embeddings_folder, index_folder=index_folder)

    assert os.path.exists(index_folder + "/image.index")
    assert os.path.exists(index_folder + "/text.index")

    indice_path = os.path.join(test_folder, "indices_paths.json")
    with open(indice_path, "w") as f:
        f.write('{"example_index": "' + index_folder + '"}')

    p = subprocess.Popen(
        f"clip-retrieval back --port=1239 --indices_paths='{indice_path}' --enable_mclip_option=False",
        shell=True,
        stdout=subprocess.PIPE,
    )
    for i in range(8):
        try:
            time.sleep(10)
            r = requests.post(
                "http://localhost:1239/knn-service",
                json={"text": "cat", "modality": "image", "num_images": 10, "indice_name": "example_index"},
            )
            _ = r.json()
            assert r.status_code == 200
            break
        except Exception as e:
            if i == 7:
                raise e
