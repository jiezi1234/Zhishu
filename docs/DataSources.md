## 一些可能会用到的数据源

- 医疗MCP服务器 https://github.com/JamesANZ/medical-mcp 
 
- 北京市医疗定点机构信息 https://data.beijing.gov.cn//zyml/ajg/sybj/35f0aff566994338b98be000d3aaa0c7.htm ，
数据已下载至 data\医疗机构基本信息2023-03-29.csv

- 高德地图MCP https://pypi.org/project/amap-mcp-server/

- 百度地图MCP https://github.com/baidu-maps/mcp

- 医疗百科 https://www.yixue.com/ ，可使用类似于 https://www.yixue.com/北京协和医院 ，查看北京协和医院信息，包含地址，联系电话，官方网站（可能过时）等

智能就医调度 Skill

产品定位
面向普通用户的AI 驱动智能就医调度助手，基于 MCP（Model Context Protocol）服务与多源医疗 / 地理数据，为用户提供「从症状到就医」的全链路决策支持，解决用户 “不知道挂什么科、去哪看病、怎么去、多久到” 的核心痛点。
核心目标
输入：用户当前地址 + 病情 / 症状描述
输出：结构化、可执行的个性化就医方案
核心价值：用 AI 替代用户自主信息检索，实现「症状智能分诊→医院精准匹配→路线最优规划→就医全流程指引」的一站式服务

核心流程
1 用户输入病情症状等信息，调用 https://www.yixue.com/常见病自测/ 初步判断（例如用户发热时，查看 https://www.yixue.com/常见病自测/常见症状辨病/发热 ，依据其中信息判断用户病情），若认为用户提供信息不足，向用户发起询问，再继续查询
2 初步判断后，向用户询问其所在地址，从 data\医疗机构基本信息2023-03-29.csv 中查询附近的医院，搜集几个最近的医院让用户选择。用户选择后，agent借助 https://www.yixue.com/ 查找目标医院官网（例如，可使用 https://www.yixue.com/北京协和医院 ，查看北京协和医院信息）再借助医院官网查询挂号信息，大部分医院禁止自动程序挂号，因此只需要搜集足够挂号信息即可
3 使用百度地图提供的skill规划路线，安装方式如下：
    安装 `baidu-ai-map` skill（`npx clawhub install baidu-ai-map`）并配置我提供的 `BAIDU_MAP_AUTH_TOKEN`；优先使用官方推荐且尽量持久化的方式，否则再用环境变量；完成后必须自行验证 skill 与 token 已生效；遇到权限、网络、依赖或报错请继续排查，仅在必须时询问；不要回显完整 token，最后只简要汇报安装是否成功、token 是否生效、配置是否持久化。我的 `BAIDU_MAP_AUTH_TOKEN`="sk-ap-Fg3fzRn5P7SfkyG38kdJ4KtI4NQ3DCHxDQ6iqUJYWp1J3JUFRhUYJWtaFGs4VoPY"
4 向用户提供点击后直接进入挂号界面的URL ，告知用户该挂哪个号
5 用户表明挂完号后，为其提供通行方案 
6 本地记忆，由于用户很可能下次还会选择相同医院，提供方案的同时也在本地持久存储医院名，官网或其他信息门户，挂号URL，出行方案。也记录用户明确厌恶的医院，加入黑名单。上面各数据源也并非100%正确，发现错误后，在本地记录错误及修正