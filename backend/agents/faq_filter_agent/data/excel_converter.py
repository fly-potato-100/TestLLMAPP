import pandas as pd
import argparse # 导入 argparse 模块
import json

class ExcelConverter:
    """
    此类用于将 Excel 文件中的数据转换为特定的 JSON 结构。
    """
    def __init__(self, excel_file_path: str):
        """
        初始化转换器。

        Args:
            excel_file_path: Excel 文件的路径。
        """
        self.excel_file_path = excel_file_path
        self.data = None
        self.processed_data = [] # 初始化为空列表

    def read_excel(self, sheet_name=0):
        """
        读取 Excel 文件。

        Args:
            sheet_name: 要读取的工作表名称或索引，默认为第一个工作表。
        """
        try:
            self.data = pd.read_excel(self.excel_file_path, sheet_name=sheet_name)
            print(f"成功读取 Excel 文件: {self.excel_file_path}")
        except FileNotFoundError:
            print(f"错误: 文件未找到 {self.excel_file_path}")
            self.data = None
        except Exception as e:
            print(f"读取 Excel 文件时出错: {e}")
            self.data = None

    def _process_row(self, row):
        """
        处理单行数据。
        (此处的具体解析和转换逻辑待实现)
        """

        row_values = []
        # 遍历前6列
        for col in range(6):
            # 使用 .iloc 进行位置索引，避免 FutureWarning
            cell_value = row.iloc[col] 
            # 使用 pd.notna() 检查是否为有效值 (非 None 和非 NaN)
            if pd.notna(cell_value):
                # 先转换为字符串，再去除首尾空格
                cell_value_str = str(cell_value).strip()
                if len(cell_value_str) > 0:
                    row_values.append(cell_value_str)

        # 打印row_values，但是除去倒数第一列
        #print(row_values[:-1])
        return row_values

    def process_rows(self):
        """
        遍历并处理 Excel 文件中的所有行。
        """
        if self.data is None:
            print("错误: 数据未加载，请先调用 read_excel()")
            return

        # 直接在遍历时构建 self.processed_data
        for index, row in self.data.iterrows():
            # 跳过表头 (假设第一行是表头)
            #if index == 0: 
            #    continue

            processed_row_data = self._process_row(row)
            if processed_row_data:
                # ---- 将合并逻辑移到此处 ----
                if len(processed_row_data) < 2:
                    print(f"警告: 跳过无效行 (少于一个键和一个值): {processed_row_data}")
                    continue

                keys = processed_row_data[:-1]
                value = processed_row_data[-1]

                current_level = self.processed_data # 从根列表开始
                for i, key in enumerate(keys):
                    found_node = None
                    # 在当前层级查找具有相同 category_desc 的节点
                    for node in current_level:
                        if node.get("category_desc") == key:
                            found_node = node
                            break

                    is_last_key = (i == len(keys) - 1)

                    if found_node:
                        # 找到节点
                        if is_last_key:
                            # 如果是最后一个 key，设置 answer
                            found_node["answer"] = value
                            # 如果之前有 sub_category，移除它，因为现在是叶子节点
                            found_node.pop("sub_category", None)
                        else:
                            # 如果不是最后一个 key，确保有 sub_category 并进入下一层
                            if "sub_category" not in found_node:
                                # 如果节点之前是叶子节点 (有 answer)，移除 answer
                                found_node.pop("answer", None)
                                found_node["sub_category"] = []
                            current_level = found_node["sub_category"]
                    else:
                        # 未找到节点，创建新节点
                        new_node = {
                            "category_key": len(current_level) + 1,
                            "category_desc": key
                        }
                        current_level.append(new_node) # 将新节点添加到当前列表

                        if is_last_key:
                            # 如果是最后一个 key，添加 answer
                            new_node["answer"] = value
                        else:
                            # 如果不是最后一个 key，添加空的 sub_category 列表，并进入下一层
                            new_node["sub_category"] = []
                            current_level = new_node["sub_category"]
                # ---- 合并逻辑结束 ----

        print("数据结构构建完成。")

    def dump_processed_data(self, output_file_path: str):
        if output_file_path is not None and len(output_file_path) > 0:
            # 写入文件
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(self.processed_data, f, indent=4, ensure_ascii=False)
            print(f"数据已保存到 {output_file_path}")
        else:
            # 打印到控制台
            print(json.dumps(self.processed_data, indent=4, ensure_ascii=False))

# 示例用法
if __name__ == "__main__":
    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(description='将 Excel 文件转换为 JSON 格式。')
    parser.add_argument('excel_file', type=str, help='要转换的 Excel 文件路径')
    parser.add_argument('--sheet', default=0, help='要读取的工作表名称或索引 (默认为 0)')
    parser.add_argument('--output', default=None, help='输出文件路径 (默认为 None)')

    # 解析命令行参数
    args = parser.parse_args()

    # 使用从命令行获取的文件路径创建转换器实例
    converter = ExcelConverter(args.excel_file)
    converter.read_excel(sheet_name=args.sheet)
    if converter.data is not None:
        converter.process_rows()
        converter.dump_processed_data(args.output)
