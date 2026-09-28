# -*- coding: utf-8 -*-
from 专项生成测试集评测公共函数 import run_special_eval

if __name__ == "__main__":
    run_special_eval(
        input_csv_name="非结构化问答评测集.csv",
        output_dir_name="非结构化文本评测结果集",
        report_title="非结构化文本评测结果集"
    )
