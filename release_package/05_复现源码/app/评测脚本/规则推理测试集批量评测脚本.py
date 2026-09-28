# -*- coding: utf-8 -*-
from 专项生成测试集评测公共函数 import run_special_eval

if __name__ == "__main__":
    run_special_eval(
        input_csv_name="规则推理测试集.csv",
        output_dir_name="规则推理测试集评测结果",
        report_title="规则推理测试集评测结果"
    )
