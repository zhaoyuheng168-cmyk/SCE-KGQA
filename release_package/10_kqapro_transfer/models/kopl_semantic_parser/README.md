---
language:
- en
pipeline_tag: text2text-generation
tags:
- semantic parsing
- bart
- KoPL
---
# Model Card for Model ID

<!-- Provide a quick summary of what the model is/does. -->

This model fine-tuned from Bart-base model for semantic parsing task which converts natural language question into logic forms named KoPL program. The model is fine-tuned on [KQA Pro dataset](https://aclanthology.org/2022.acl-long.422/).

## Model Details

### Model Description
- **Model type:** Semantic parsing model
- **Language(s) (NLP):** English
- **Finetuned from model:** Bart-base

## How to Get Started with the Model

Refer code below to get started with the model.

[Github Link](https://github.com/THU-KEG/DiaKoP/blob/main/backend-src/semantic_parser.py)

## Citation
**BibTeX:**  
```
@inproceedings{cao-etal-2022-kqa,
    title = "{KQA} Pro: A Dataset with Explicit Compositional Programs for Complex Question Answering over Knowledge Base",
    author = "Cao, Shulin  and
      Shi, Jiaxin  and
      Pan, Liangming  and
      Nie, Lunyiu  and
      Xiang, Yutong  and
      Hou, Lei  and
      Li, Juanzi  and
      He, Bin  and
      Zhang, Hanwang",
    editor = "Muresan, Smaranda  and
      Nakov, Preslav  and
      Villavicencio, Aline",
    booktitle = "Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)",
    month = may,
    year = "2022",
    address = "Dublin, Ireland",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2022.acl-long.422",
    doi = "10.18653/v1/2022.acl-long.422",
    pages = "6101--6119",
    abstract = "Complex question answering over knowledge base (Complex KBQA) is challenging because it requires various compositional reasoning capabilities, such as multi-hop inference, attribute comparison, set operation, etc. Existing benchmarks have some shortcomings that limit the development of Complex KBQA: 1) they only provide QA pairs without explicit reasoning processes; 2) questions are poor in diversity or scale. To this end, we introduce KQA Pro, a dataset for Complex KBQA including around 120K diverse natural language questions. We introduce a compositional and interpretable programming language KoPL to represent the reasoning process of complex questions. For each question, we provide the corresponding KoPL program and SPARQL query, so that KQA Pro can serve for both KBQA and semantic parsing tasks. Experimental results show that state-of-the-art KBQA methods cannot achieve promising results on KQA Pro as on current datasets, which suggests that KQA Pro is challenging and Complex KBQA requires further research efforts. We also treat KQA Pro as a diagnostic dataset for testing multiple reasoning skills, conduct a thorough evaluation of existing models and discuss further directions for Complex KBQA. Our codes and datasets can be obtained from \url{https://github.com/shijx12/KQAPro_Baselines}.",
}
```