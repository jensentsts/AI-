# 焚诀

个人 AI 辅助科研与项目开发提示词、规范及文献检索工具集。

> 作者按：本仓库试图教会GPT如何产出一篇 **及格** 的论文，以及 gemini 嵌入到工作流的使用方法。
> 这意味着，使用者仍然需要对论文的很多细节进行打磨。不过好在不再是从零开始。
> 我要求GPT不添加AI Acknowledgements，不是我主张对AI的使用进行隐瞒，也不代表着我个人进行了不当的信息遮蔽，而是因为GPT总是因为这个内容自动地存在于论文中，而防御性过强。此举是为了在论文撰写过程中尽可能彻底、全面地去除GPT的过度防御问题。

## 依赖 Skills

配合本仓库规范使用前，需配置以下 Skills：

- **`humanizer`**（`/humanizer`）：用于在论文稿件形成后、交付前进行表述润色与优化。
- **`scientific-brainstorming`**（`/scientific-brainstorming`）：用于在研究与论文创作阶段进行创新点构思、评估与重构。

## 仓库内容

- `初始化.txt` / `初始化-精简版.txt`：项目初始化与代码工程规范提示词。 （作者按：这个是26年上半年的产物了，比较古早。）
- `论文要求.txt`：学术论文写作、排版、图表与创新点要求。
- `paper_search_tools/`：支持 arXiv / Web of Science / Elsevier 的多源论文检索、下载与文本提取工具，详见 [`paper_search_tools/README.md`](paper_search_tools/README.md)。（作者按：可以轻松地扩展，使它支持ieee、知网等检索，将固化的流程转换为被调用的代码，能适当地降低额度消耗。）

## License

[MIT](LICENSE)
