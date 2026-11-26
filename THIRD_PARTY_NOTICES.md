# 第三方代码与资源许可说明

本项目自行编写的代码和文档采用根目录 [MIT License](LICENSE)，已有单独许可或来源声明的内容除外。第三方代码、依赖、字体、模型权重、数据集、论文和示例媒体继续适用各自许可；根目录 LICENSE 不会改变它们的授权条件。

## 仓库内保留的第三方代码与许可

| 内容 | 来源与许可 | 本地说明 |
| --- | --- | --- |
| React Bits 组件及本地适配 | [React Bits](https://github.com/DavidHDev/react-bits)，本仓库保留版本标注为 MIT + Commons Clause License Condition v1.0 | [原许可](front/src/components/react-bits/LICENSE.md)、[上游版本与本地改动](front/src/components/react-bits/SOURCE.md) |
| Guten OCR 相关组件 | [Guten OCR](https://github.com/gutenye/ocr)，MIT | [许可原文](front/public/ocr/LICENSE-GutenOCR.txt) |
| ONNX Runtime | [ONNX Runtime](https://github.com/microsoft/onnxruntime)，MIT | [许可原文](front/public/ocr/LICENSE-ONNXRuntime.txt) |
| PaddleOCR 相关内容 | [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)，Apache-2.0 | [许可原文](front/public/ocr/LICENSE-PaddleOCR.txt) |
| OpenCV 相关内容 | [OpenCV](https://github.com/opencv/opencv)，本仓库随附 Apache-2.0 许可 | [许可原文](front/public/ocr/LICENSE-OpenCV.txt) |
| 随附的 KaTeX 数学渲染组件 | [KaTeX](https://github.com/KaTeX/KaTeX)，MIT | [许可原文](backend/modules/math_render/vendor/LICENSE) |

React Bits 的上述许可带有额外限制，不是标准 MIT；它允许按原条款用于应用、网站或产品，同时限制组件本身的销售、再许可或再分发。具体范围以保留的许可原文为准，不能把这些文件重新标记为本项目的 MIT 代码。

## 安装时取得或单独运行的依赖

- **alcedo**：可选媒体链接解析组件，安装脚本默认固定为 0.2.0，由 CLI 或 HTTP 接入。本项目编写适配层，不将上游解析器作为自有实现。程序包中的 MIT LICENSE 与上游版权声明继续有效，安装包分发时保留。[上游仓库](https://github.com/hiyufan/alcedo)，[安装脚本](scripts/install-alcedo.sh)，[适配层](backend/modules/video_source/alcedo.py)。
- **GSAP**：按安装版本附带的 GSAP 许可使用，不能因本项目采用 MIT 而将其标为 MIT。[许可页面](https://gsap.com/standard-license/)。
- **Inter、JetBrains Mono、Unbounded 字体**：由对应 `@fontsource` 包提供，包内标注 OFL-1.1。分发字体时保留实际包内的许可与版权声明。
- **其他 Python、JavaScript 依赖及 ffmpeg**：适用各自安装版本或二进制构建的许可。项目依赖声明不替代依赖包中的 LICENSE、NOTICE 或版权声明。

## 模型、资料与媒体

识别模型权重、评测数据集、论文和视频图片等素材不因被本项目使用而获得新的 MIT 授权。它们的使用与再分发范围应按来源说明及实际许可分别确认。演示媒体的来源与处理记录见 [媒体说明](docs/media/README.md)。

本文件列出项目中已明确识别的第三方内容及许可入口，不是所有传递依赖的完整 SBOM。制作安装包或提交材料时，应随实际包含的第三方内容保留相应许可和声明。
