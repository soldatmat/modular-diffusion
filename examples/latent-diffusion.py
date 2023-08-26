import sys
from pathlib import Path

import torch

sys.path.append(".")  # TODO: remove after release
sys.path.append("examples")

import diffusion
from diffusion.data import Embedding
from diffusion.loss import Simple
from diffusion.net import Transformer
from diffusion.noise import Gaussian
from diffusion.schedule import Sqrt

from utils import download, tokenize

file = Path(__file__)
input = file.parent / "data/in/e2e"
output = file.parent / "data/out" / file.stem
output.mkdir(parents=True, exist_ok=True)
torch.set_grad_enabled(False)
torch.set_float32_matmul_precision("high")

if not input.exists():
    url = "https://raw.githubusercontent.com/tuetschek/e2e-dataset/master/trainset.csv"
    input.mkdir(parents=True)
    download(url, input / "text")
    text = (input / "text").read_text().replace("\n ", "").split("\n")[1:-1]
    text = "\n".join(line.rsplit('",', 1)[1][1:-1] for line in text)
    (input / "text").write_text(text)
    tokenize(input / "text", input / "ids", size=2048, pad=True)
    (input / "text").unlink()

v = (input / "vocabulary").read_text().split()[::2]
x = (input / "ids").read_text().split("\n")
x = [[int(w) for w in l] for s in x if len(l := s.split()) <= 128]
x = torch.tensor([s + [1] * (128 - len(s)) for s in x])

model = diffusion.Model(
    data=Embedding(x, count=len(v), dimension=32, batch=64, shuffle=True),
    schedule=Sqrt(2000),
    noise=Gaussian(parameter="x", variance="fixed"),
    loss=Simple(parameter="x"),
    net=Transformer(input=32, width=1024, depth=16, heads=16),
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
)

if (output / "model.pt").exists():
    model.load(output / "model.pt")
epoch = sum(1 for _ in output.glob("[0-9]*"))

for epoch, loss in enumerate(model.train(epochs=10000), epoch + 1):
    *_, z = model.sample(batch=10)
    z = ["".join(v[w] for w in s).replace("▁", " ").lstrip() for s in z.int()]
    (output / f"{epoch}-{loss:.2e}.txt").write_text("\n".join(z))
    model.save(output / "model.pt")