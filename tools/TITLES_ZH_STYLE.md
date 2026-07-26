# 老照片标题中译规范（务必严格遵守）

项目：`/Users/jinbin/Documents/codeup/china-old-photos`（清末民国老照片图集，2041 张）
你的任务：把分配给你的英文原题译成中文标题，输出一个 JSON 文件。

## 最高原则：克制直译

**贴着英文原文译，绝不添加原文没有的信息。** 用户明确要求"不要发挥太多"。

正确示例：
- `Gate` → `门`（不要擅自写成"城门"）
- `Forts` → `炮台`（不要写"海边山丘上的炮台"）
- `Statue` → `塑像`
- `Street Scene [1908]` → `街景 [1908]`
- `Fishing with net from dockside` → `码头边撒网捕鱼`
- `Horse & Cow Guardians` → `牛头马面`（这是该词的中文本名，不算发挥）
- `Chinese Prisoner in Stocks` → `戴木枷的囚犯`

错误示例（过度发挥，禁止）：
- `Church Front` → ~~`大三巴牌坊（圣保禄教堂遗址，澳门标志建筑）`~~
- `Boat` → ~~`静静停泊在运河上的乌篷船`~~

## 具体规则

1. **地名音译能确证的还原成中文**（这是还原不是发挥）：
   `Chien Men`→前门、`Lin Yin`→灵隐、`Lai Fung Tah`→雷峰塔、`Ya Ven`→衙门、
   `Liang Ting`→凉亭、`Pei Hai`→北海、`Tung Yueh Miao`→东岳庙、`Wan Shou Shan`→万寿山。
   **拿不准的一律保留英文原样**，例如 `Pusiang Boys` → `Pusiang 男童`、
   `Six Harmonies Pagoda Telar` → `六和塔·Telar`。宁可保留英文，不可猜译。

2. **人名**：有通行中译的历史人物用中文（Gamble→甘博、Morrison→马礼逊、Camoes→贾梅士）；
   其余一律保留英文原样，如 `J.H. Arthur`、`R.F. Fitch 夫妇`、`Betty 坐在椅中`、`Dr. Main 乘驴车`。

3. **档案编号一律省略**（英文原题会在页面上并列显示，不会丢失信息）：
   `Street in Peking LCCN2014688957` → `北京街景`
   `Bundesarchiv Bild 102-13036 Shanghai Drahtsperren um Europäerviertel` → `上海·欧洲人居住区的铁丝网障`
   即：去掉 LCCN/Bundesarchiv Bild/accession 之类纯编号，只译描述部分。

4. **非英语原题（德语、法语等）按语义译**。

5. **`Untitled lantern slide` 等无题照片**：必须先看图再命名。
   缩略图路径 = `thumbs/` + 该条的 path，例如 path 为 `beijing/gamble/RL_xxx.jpg`，
   就 Read `/Users/jinbin/Documents/codeup/china-old-photos/thumbs/beijing/gamble/RL_xxx.jpg`。
   格式统一为 `无题幻灯片·<最简画面描述>`，如 `无题幻灯片·河上摇橹的船`、`无题幻灯片·课桌前的学童`。
   描述要短（6–10 字），只写看得见的东西，不推测地点身份。
   **只有无题照片需要看图**，其余有英文原题的一律直接译，不要看图（省时间）。

6. **长度**：尽量控制在 16 字以内；原题本身很长很啰嗦的（如 `A group of Chinese men eating around a table`
   → `一群中国男子围桌用餐`）照译即可，不必强行压缩。

7. **重复标题不要自己加"之一/之二"编号**，原样输出，编号由主流程统一处理。

8. **只读不写仓库**：不要修改仓库里任何文件（尤其 tools/*.json、gallery.html），
   只把结果写到指定的输出文件。

## 输入与输出

- 输入文件是一个 JSON 数组，每项为 `[path, 英文原题]`。
- 输出：一个 JSON 对象 `{path: 中文标题}`，**必须覆盖输入的每一条，一条不漏**，
  条数必须与输入完全一致。写到指定输出路径，UTF-8，`ensure_ascii=False`。
- 写完后自查：`python3 -c "import json;a=json.load(open('输入'));b=json.load(open('输出'));print(len(a),len(b));print([p for p,_ in a if p not in b][:5])"`
  条数必须相等且缺失列表为空。
