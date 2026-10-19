# 科普核验评测：待确认标签

每条说法给了建议标签和依据。确认无误就在 `backend/evals/factcheck.json` 里把该条目的 `reviewed` 改成 `true`；
标签不对就改 `label`，并在 `evidence` 里放你依据的权威链接。也可以直接把修改意见发给 Claude。

标签：正确 correct · 部分正确 partial · 错误 wrong · 无法核实 unverifiable

## ⬜ 待确认 · vinegar-bp · 实测：电视剧“西北锤王”里的喝醋降血压，是真的吗？

https://www.bilibili.com/video/BV1Nu4m1T7u8（嘴强开箱 · 104637 播放）

- **c1** 喝醋不能降低血压
  - 原话：「这怎么还又高了呢」
  - 标签：**正确**（correct）— 多个权威来源明确称喝醋不能降血压
  - 出处：http://jiankang.cctv.com/2019/04/22/ARTIZofRZFCXjw5FhDmw8ANJ190422.shtml
  - 出处：https://www.fuwaihospital.org/News/Articles/Index/202020
  - 出处：https://piyao.kepuchina.cn/h5/rumordetail?id=ZzLO
- **c2** 大量喝醋会让胃难受
  - 原话：「喝多了其实这个胃还是挺难受的」
  - 标签：**正确**（correct）— 多个权威来源均指出大量喝醋会刺激胃黏膜、引发胃部不适
  - 出处：https://wsjk.tj.gov.cn/JKJY5233/JKZS7782/202008/t20200828_3579899.html
  - 出处：http://health.cnr.cn/jkgdxw/20170328/t20170328_523680326_1.shtml
  - 出处：http://health.cnr.cn/jkgdxw/20181012/t20181012_524382921.shtml
  - 出处：https://health.cnr.cn/jkgdxw/20260109/t20260109_527488365.shtml#1
  - 出处：http://gzdjk.gog.cn/system/2018/09/07/016792498.shtml
- **c3** 不要尝试靠喝醋降血压
  - 原话：「大家千万不要尝试」
  - 标签：**正确**（correct）— 多个权威来源均指出喝醋不能降血压，与说法一致
  - 出处：http://jiankang.cctv.com/2019/04/22/ARTIZofRZFCXjw5FhDmw8ANJ190422.shtml
  - 出处：https://www.fuwaihospital.org/News/Articles/Index/202020
  - 出处：https://piyao.kepuchina.cn/h5/rumordetail?id=ZzLO

## ⬜ 待确认 · breathing-bp · 两分钟把高血压的原理给你讲得明明白白！

https://www.bilibili.com/video/BV1KA411N7pk（泽桥医生 · 445691 播放）

- **c1** 高血压会使血管壁受压增加，导致血管壁变脆变硬甚至出现裂纹
  - 原话：「原本有弹性的血管壁变脆变硬」
  - 标签：**部分正确**（partial）— 来源支持高血压致血管僵硬，但未提“变脆、裂纹”，属夸大
  - 出处：https://health.cnr.cn/jkgdxw/20231011/t20231011_526447106.shtml#1
  - 出处：https://www.ahajournals.org/doi/10.1161/HYPERTENSIONAHA.111.187021#1
- **c2** 血管硬化是不可逆的
  - 原话：「血管的硬化是不可逆的」
  - 标签：**正确**（correct）— 权威卫健委及医学来源均称动脉硬化不可逆
  - 出处：http://wjw.xinjiang.gov.cn/hfpc/jkcj/202208/6cb9466a67f34441aced82bf61b60aaf.shtml
  - 出处：https://m.dayi.org.cn/qa/83505.html#1
  - 出处：https://m.dayi.org.cn/qa/343563.html#1
- **c3** 预防高血压应拒绝高盐高脂饮食并加强锻炼
  - 原话：「请拒绝高盐高脂饮食」
  - 标签：**部分正确**（partial）— 来源支持高盐高脂升压，但未涉及锻炼，属遗漏条件
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S0271531781800280#1
  - 出处：https://pure.johnshopkins.edu/en/publications/association-of-fat-and-salt-intake-with-blood-pressure-in-urban-a-5/#1
  - 出处：https://pubmed.ncbi.nlm.nih.gov/12433862/#1
- **c4** 已得高血压者应调整生活习惯，必要时用药物控制
  - 原话：「必要时以药物控制」
  - 标签：**正确**（correct）— 权威来源均支持生活方式干预加必要时药物控制血压
  - 出处：https://www.msdmanuals.com/ja-jp/professional/04-%e5%bf%83%e8%a1%80%e7%ae%a1%e7%96%be%e6%82%a3/%e9%ab%98%e8%a1%80%e5%9c%a7/%e9%ab%98%e8%a1%80%e5%9c%a7?media=hybrid&client=vin#3
  - 出处：https://www.yywsb.com/article/70518.html

## ⬜ 待确认 · leftovers · 颠覆认知！隔夜菜到底能不能吃？24小时冷藏实测！【老爸评测】

https://www.bilibili.com/video/BV1mV411y7kA（老爸评测 · 1355551 播放）

- **c1** 隔夜菜冷藏前先回锅加热再放入冰箱
  - 原话：「隔夜菜你要加热一下以后再冷藏放入冰箱」
  - 标签：**错误**（wrong）— 来源建议尽快分装冷藏，反对整锅反复回锅加热
  - 出处：https://health.ftvnews.com.tw/news/detail/2026215W0253?utm_source=yahoo&utm_medium=InArticl
  - 出处：http://wjw.yangzhou.gov.cn/zfxxgk/fdzdgk/ywgz/jkxj/art/2026/art_e5019ac78e4d405c878d7606b8cce1bd.html
- **c2** 剩菜最好剩肉菜，不要剩蔬菜、凉拌菜和海鲜
  - 原话：「最好剩下的是肉菜，不要剩蔬菜凉拌菜和海鲜」
  - 标签：**正确**（correct）— 权威来源均建议剩荤不剩素，且凉拌菜、海鲜不宜剩
  - 出处：http://ylxf.1237125.cn/topicweb/emag/zftd/page/2/2018-03/10/71/2018031071_pdf.pdf#1#1
  - 出处：https://xa8yuan.com/default/detaile/22090115cLLER
  - 出处：https://ggw.nantong.gov.cn/ntsgxxydgzwyh/xstd/content/e136f201-187a-4a0f-8a07-dd4fc6bc9562.html
- **c3** 热菜要趁热放冰箱，微生物滋生最少且对冰箱无害
  - 原话：「热菜要趁热放冰箱，微生物的滋生量是最少的」
  - 标签：**正确**（correct）— 多个权威来源一致指出应趁热密封放冰箱，减少细菌繁殖且对现代冰箱耗电影响极小
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7326983904517095424#1#1
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?id=7395527173370695680
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?id=7111408587511238656
- **c4** 隔夜菜要吃时需彻底加热，100℃回锅3分钟
  - 原话：「要彻底加热后再食用，高温100℃回锅3分钟」
  - 标签：**正确**（correct）— 多个权威来源均支持100℃沸腾3分钟以上彻底加热
  - 出处：http://health.cnr.cn/jkgdxw/20200826/t20200826_525227494.shtml
  - 出处：https://www.jxjjsdsrmyy.cn/101/202602/t20260226_7170957.html
  - 出处：http://jhjk.ahnmc.com/resfile/2017-01-25/61/61.pdf#1#1

## ⬜ 待确认 · acid-alkaline · 酸碱理论

https://www.bilibili.com/video/BV1LN411u7pz（科学小视 · 166368 播放）

- **c1** 在水溶液中电离出的阳离子全部都是氢离子的物质叫酸
  - 原话：「电离出的阳离子全部都是氢离子」
  - 标签：**正确**（correct）— 科普中国多条来源明确给出该阿伦尼乌斯酸定义
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?from=1&id=6969140853272244224&is_self=2
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=6972625635187023872#1
  - 出处：https://www.kepuchina.cn/article/articleinfo?business_type=100&classify=0&ar_id=288335#1
- **c2** 在水溶液中电离出的阴离子全部都是氢氧根离子的物质叫碱
  - 原话：「阴离子全部都是氢氧根离子」
  - 标签：**正确**（correct）— 多个权威来源明确给出该Arrhenius碱定义
  - 出处：https://xuewen.cnki.net/R2008120650002898.html
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?from=1&id=6969140853272244224&is_self=2
  - 出处：http://edu.hqwxedu.com/web_news/html/2015-6/1435540937.html
- **c3** 凡是能给出质子的物质都是酸
  - 原话：「凡是能给出质子的物质都是酸」
  - 标签：**正确**（correct）— 多个权威来源明确：能给出质子的物质都是酸
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=6972625739780157440
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?from=1&id=6969140853272244224&is_self=2
  - 出处：https://www.kepuchina.cn/article/articleinfo?ar_id=583753&business_type=100
- **c4** 凡是能接受电子对的物质都是酸
  - 原话：「凡是能接受电子对的物质都是酸」
  - 标签：**正确**（correct）— 多个权威来源一致定义路易斯酸为电子对接受体
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?id=6972627039280402432
  - 出处：https://xuewen.cnki.net/r2006090130000285.html
  - 出处：https://wiki.cnki.com.cn/HotWord/1527682.htm

## ⬜ 待确认 · bone-soup · 为什么有人说喝汤没营养？建议看到最后【食录】

https://www.bilibili.com/video/BV1B7oXYhEac（赛博小食录 · 907108 播放）

- **c1** 骨头汤的钙含量与普通自来水相当，补钙效果和喝自来水差不多
  - 原话：「补钙效果居然跟喝自来水差不多」
  - 标签：**正确**（correct）— 多个权威来源均称骨头汤钙含量与自来水相似，补钙效果差
  - 出处：https://wsjk.tj.gov.cn/JKJY5233/JKZS7782/202008/t20200828_3578219.html
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=eegb
  - 出处：http://kpzg.people.com.cn/n1/2025/1021/c404214-40585953.html
- **c2** 汤里的营养素含量不足食材总量的10%
  - 原话：「汤里的营养素含量甚至还不足食材总量的10%」
  - 标签：**部分正确**（partial）— 来源称汤中营养素最多10-15%，非水溶性营养素不足10%，说法大体对但遗漏条件
  - 出处：https://www.peopleapp.com/rmharticle/30019844179
  - 出处：https://sdxw.iqilu.com/share/YS0yMS0xNTMwMDk0NQ==.html
- **c3** 汤汁越乳白浓郁，脂肪含量就越高
  - 原话：「汤汁越乳白浓郁，脂肪的含量就越高」
  - 标签：**正确**（correct）— 多个权威来源一致指出汤越乳白脂肪含量越高
  - 出处：http://shipin.people.com.cn/n1/2016/0706/c85914-28527672.html
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7025940643729100800
  - 出处：https://www.piyao.org.cn/20230918/a6a0ad72fdc94a5f8e402be5d95b0329/c.html
- **c4** 痛风患者应尽量不喝肉汤
  - 原话：「痛风患者尽量不喝肉汤」
  - 标签：**正确**（correct）— 权威来源称肉汤嘌呤高，是痛风加速器，不宜喝
  - 出处：https://wsjkw.sh.gov.cn/spwsyyy/20260113/e193f1267192417ba69b414d8f09e7bc.html
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=lxmw
  - 出处：https://health.cnr.cn/jkgdxw/20171102/t20171102_524009194.shtml#1#1

## ⬜ 待确认 · brown-sugar · 这个冬天开始学会给女朋友做一碗热饮吧！女生也可以自己做！

https://www.bilibili.com/video/BV1niBiYzEwM（茄猫的罐头 · 3239440 播放）

- **c1** 生姜有补血养颜、镇静缓痛的作用
  - 原话：「生姜 补血养颜 镇静缓痛」
  - 标签：**部分正确**（partial）— 来源称生姜红糖水/姜枣汤有补气补血、美容养颜，但未直接说生姜镇静缓痛
  - 出处：https://m.dayi.org.cn/qa/188123#1
  - 出处：https://m.dayi.org.cn/qa/254453.html
  - 出处：https://m.dayi.org.cn/qa/231276#1
- **c2** 月经结束后一周是补气血的黄金期
  - 原话：「姨走后一周才是补的黄金期」
  - 标签：**正确**（correct）— 多个权威来源称经后一周/经后期是补气血最佳窗口
  - 出处：https://health.udn.com/health/amp/story/5966/9709525?from=udnamp-referralnews_ch1005artbottom
  - 出处：https://zyy.rednet.cn/content/646856/75/14590558.html
- **c3** 红豆煮食能改善心情
  - 原话：「吃完真的能让心情变好」
  - 标签：**部分正确**（partial）— 来源称红豆含B6助安定情绪、清心除烦，但未直接证实煮食改善心情，属大体对但条件不全
  - 出处：https://health.tvbs.com.tw/review/321289
  - 出处：http://health.people.com.cn/n1/2016/0524/c21471-28373884.html
  - 出处：https://my.top1health.com/Article/239/76667
- **c4** 秋冬嗓子不适可用橙子加冰糖煮茶缓解
  - 原话：「秋冬干燥 容易嗓子不舒服」
  - 标签：**部分正确**（partial）— 来源称可润喉缓解不适，但属食谱/百科，非权威医学证据
  - 出处：https://jbk.39.net/yy3/250108/p5uy3nd.html
  - 出处：https://baike.baidu.com/item/%e5%86%b0%e7%b3%96%e9%9b%aa%e6%a2%a8%e6%a9%99/17153085

## ⬜ 待确认 · pig-trotter · 阿胶、猪蹄都是劣质蛋白，这个观点偏口鱼博士不讲我还真不知道

https://www.bilibili.com/video/BV1SzBfB5Ey1（偏口鱼博士精选 · 349820 播放）

- **c1** 胶原蛋白（阿胶、猪蹄、鸡皮、鱼皮等动物皮类）都是劣质蛋白，人体不需要
  - 原话：「胶原蛋白都是劣质蛋白不是好蛋白」
  - 标签：**部分正确**（partial）— 来源称胶原蛋白为劣质蛋白、利用率低，但未说人体不需要
  - 出处：https://www.lifetimes.cn/article/484KKy5Agp9
  - 出处：https://zyj.beijing.gov.cn/ylfw/ysbj/201912/t20191223_1412077.html
- **c2** 鸡蛋、牛奶、大豆、鱼虾、鸡胸肉、牛羊肉属于优质蛋白
  - 原话：「好的就是鸡蛋、牛奶」
  - 标签：**正确**（correct）— 多个权威来源明确蛋奶肉鱼虾及大豆属优质蛋白
  - 出处：https://jiankang.cctv.cn/2026/09/10/ARTI5PLdTpy7wvu7ozwQViRl260910.shtml#1
  - 出处：https://wsjkw.sh.gov.cn/spwsyyy/20260416/5b1a56c3216148769ef4b8b710aa1e00.html
  - 出处：https://ynswsjkw.yn.gov.cn/html/2023/xuanchuankejiao_0814/17803.html
- **c3** 谷物（如大米）中的蛋白质量较差，只吃大米不吃肉不行
  - 原话：「谷物蛋白不太行啊」
  - 标签：**部分正确**（partial）— 来源指出谷物蛋白缺乏赖氨酸、消化率低，但未直接说只吃大米不行
  - 出处：https://www.nahs.org.cn/zt_10027/sydbjltd/dyjhdpjl/202306/t20230626_426422.htm
  - 出处：https://onlinelibrary.wiley.com/doi/full-xml/10.1002/fsn3.1809#3
- **c4** 一天吃两三个三四个鸡蛋没问题
  - 原话：「你就吃个两个三四个没事」
  - 标签：**部分正确**（partial）— 指南建议每日约1个，特殊人群最多3个，说法未限定条件
  - 出处：https://health.cnr.cn/sy/jd/20251222/t20251222_527468114.shtml
  - 出处：https://sykp.hebei.com.cn/system/2025/12/15/030369248.shtml

## ⬜ 待确认 · egg-yolk · 蛋黄胆固醇含量高，一天吃几个鸡蛋好？

https://www.bilibili.com/video/BV1mP4y1x7Da（刘加勇医生 · 1464562 播放）

- **c1** 吃蛋黄不会明显升高血液胆固醇
  - 原话：「对血清胆固醇的影响特别特别轻微」
  - 标签：**部分正确**（partial）— 有来源称蛋黄不升胆固醇，但ScienceDirect研究显示每日加蛋使TC/LDL显著升高，说法忽略条件
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S0899900713002116#1
  - 出处：https://wsjkw.sh.gov.cn/spwsyyy/20240125/87fff3b0b9574549b296cabc745438ab.html
- **c2** 人体胆固醇主要靠自身合成，食物摄入仅占约25%
  - 原话：「主要靠自己合成」
  - 标签：**正确**（correct）— 权威来源称食物来源约20%-33%，与约25%一致
  - 出处：http://ynswsjkw.yn.gov.cn/html/2023/xuanchuankejiao_0714/17608.html
  - 出处：https://www.health.harvard.edu/heart-health/how-its-made-cholesterol-production-in-your-body?shortlink=f1a061a3&pid=Email&c=selfserve-comms-2021&af_channel=Email&gad_source=1#1
- **c3** 一天吃两三个鸡蛋没问题
  - 原话：「一天吃两三个也没问题」
  - 标签：**部分正确**（partial）— 健康时报称健康人群每天2~3个鸡蛋可以，但权威来源建议每天不超过一个，说法遗漏条件且与部分来源不一致
  - 出处：http://www.jksb.com.cn/index.php?m=wap&a=show&catid=788&id=256254
  - 出处：https://www.massgeneralbrigham.org/zh-cn/health-wellness/are-eggs-heart-healthy#1
- **c4** 蛋黄中的卵磷脂能降低胆固醇、保护心脏
  - 原话：「它能降低胆固醇的卵磷脂」
  - 标签：**无法核实**（unverifiable）— 来源均研究大豆卵磷脂，未涉及蛋黄卵磷脂
  - 出处：https://pubmed.ncbi.nlm.nih.gov/9733225/#1
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S0021915098001324#1
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S0024320500008407
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S0955286300001157#1
  - 出处：https://nap.nationalacademies.org/read/1222/chapter/10?term=""energy+intake""#19

## ⬜ 待确认 · msg · 酒精：抱歉，安全摄入量为0的一级（类）致癌物  【医学真相】第一集

https://www.bilibili.com/video/BV1U5411Z7VH（医学科普联盟 · 5893803 播放）

- **c1** 任何种类、任何剂量的酒都对人体有害
  - 原话：「任何剂量的酒都对人体有害」
  - 标签：**正确**（correct）— 多个权威来源明确称任何剂量酒精均有害
  - 出处：https://hpdp.gov.mt/hpu/alcohol
  - 出处：https://mohw.gov.tw/cp-3790-39404-1.html
  - 出处：https://www.mayoclinic.org/healthy-lifestyle/nutrition-and-healthy-eating/in-depth/alcohol/art-20044551?srch_tag=nqypphxlk5pj3fmwgo2ew7nju73fpcjx&p=1#1
- **c2** 喝酒脸红是乙醛中毒
  - 原话：「喝酒脸红其实就是乙醛中毒」
  - 标签：**正确**（correct）— 多个权威来源明确称脸红是乙醛堆积/中毒表现
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=Dzlq
  - 出处：http://img1.kepuchina.cn/wiki/faq/201902/t20190218_981145.shtml
  - 出处：https://dxy.com/article/192932#1
  - 出处：https://health.rednet.cn/content/646040/52/16011370.html
- **c3** 适量饮酒有益健康是谎言
  - 原话：「适量饮酒有益健康的谎言」
  - 标签：**正确**（correct）— 多个权威来源均否定适量饮酒有益健康
  - 出处：http://health.cnr.cn/jkgdxw/20260418/t20260418_527590015.shtml
  - 出处：http://health.cnr.cn/jkgdxw/20210205/t20210205_525407817.shtml#1
  - 出处：https://www.change4health.gov.hk/en/alcohol_aware/facts/topics/heart_attack.html
- **c4** 酒不会越喝越暖，只会越喝越寒
  - 原话：「酒不会越喝越暖 相反只会越喝越寒」
  - 标签：**正确**（correct）— 权威来源均指出喝酒散热更快、酒后寒，与说法一致
  - 出处：http://health.cnr.cn/jkgdxw/20181010/t20181010_524381073.shtml#1
  - 出处：https://www.sh-na.com/portal/article/index/id/4084/cid/183.html

## ⬜ 待确认 · microwave · 为什么微波炉不能同时加热两颗葡萄？放进去后，可怕的一幕发生了

https://www.bilibili.com/video/BV1XZgzzGEUP（冷科普 · 1385300 播放）

- **c1** 微波炉不能同时加热两颗葡萄
  - 原话：「为什么微波炉不能同时加热两颗葡萄」
  - 标签：**错误**（wrong）— 来源明确警告两枚葡萄紧挨加热会着火爆炸，与说法相反
  - 出处：https://stb.mae.edu.cn/site/yard/875/resource/34159
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=6791538300448993280#1
- **c2** 金属制品不能放进微波炉加热
  - 原话：「首先是金属制品」
  - 标签：**正确**（correct）— 多个权威来源均指出金属器皿不可进微波炉，会反射微波、产生火花甚至起火
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=6969019787556155392
  - 出处：https://www.kepuchina.cn/more/202107/t20210731_3014381.shtml
  - 出处：https://www.cfs.gov.hk/sc_chi/programme/programme_rafs/programme_rafs_ft_02_01.html#1
- **c3** 带壳或薄膜的食物（如鸡蛋、火腿肠）不能用微波炉加热
  - 原话：「有壳和有薄膜的不行」
  - 标签：**部分正确**（partial）— 来源支持带壳/薄膜食物易爆，但未涵盖火腿肠等所有情况，说法绝对化
  - 出处：https://www.kepuchina.cn/article/articleinfo?ar_id=398939&business_type=100&classify=0#1
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7404917150636322816
- **c4** 不要用微波炉烧水
  - 原话：「也不要用微波炉烧水」
  - 标签：**部分正确**（partial）— 来源称微波炉能烧水但不安全，说法绝对化遗漏条件
  - 出处：https://www.kepuchina.cn/article/articleinfo?ar_id=444273&business_type=100&classify=0
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?from=1&id=7002683248556765184&is_self=2
  - 出处：https://www.cfs.gov.hk/sc_chi/programme/programme_rafs/programme_rafs_ft_02_01.html#1

## ⬜ 待确认 · mung-bean · 一碗绿豆汤，毁了你一夏天的努力！

https://www.bilibili.com/video/BV1bduV6yE2e（随心Kan世界 · 32721 播放）

- **c1** 绿豆解暑的有效成分主要在绿豆皮里，不在绿豆肉里
  - 原话：「绿豆解暑的命根子在皮上」
  - 标签：**正确**（correct）— 多个权威来源均指出解暑有效成分多酚类主要在绿豆皮中
  - 出处：https://health.cnr.cn/jkgdxw/20260731/t20260731_527738706.shtml#1
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?type=2&id=6654093124466143232
  - 出处：https://www.kepuchina.cn/article/articleinfo?ar_id=512230&business_type=100&classify=0#1
  - 出处：https://www.dongfangyy.com.cn/Html/News/Articles/12306.html
  - 出处：https://www.kepuchina.cn/2016zt/kpzgldyytc/sqxc/lbdqsjs/02/201801/t20180118_535848_8.shtml
- **c2** 煮绿豆汤时加糖会降低解暑效果
  - 原话：「加糖就是降效果」
  - 标签：**无法核实**（unverifiable）— 来源仅提糖友/脂肪肝不宜加糖，未涉及加糖降低解暑效果
  - 出处：https://www.acondiabetescare.com.cn/health_cont.aspx?id=740
  - 出处：https://jbk.39.net/zfg/231027/l5ijj5x.html
  - 出处：http://www.lygcdc.cn:19000/cms/document/2936.html
- **c3** 吃降压药、降糖药、抗凝药后两小时内不能喝绿豆汤
  - 原话：「吃药后两小时内碰都别碰绿豆汤」
  - 标签：**部分正确**（partial）— 来源称大量饮用且间隔不足可影响药效，但未明确两小时界限，说法绝对化
  - 出处：http://jyb.ncrbw.cn/h5/html5/2026-07/27/content_143745_3676880.htm
  - 出处：https://www.psmchina.cn/safe_medicines_information/safe_medicines_knowledge/jbcs/12684
- **c4** 脾胃虚寒的人喝绿豆汤不要放冰，可加两片生姜
  - 原话：「别放冰 加两片生姜」
  - 标签：**正确**（correct）— 权威来源称脾胃虚寒者绿豆汤不宜冰镇，可加生姜中和寒性
  - 出处：https://www.fshtcm.com.cn/zyy2023/jkjt/202607/t20260724_6425609.html
  - 出处：http://www.hnszyyxh.org/20260813/6MoFG3E0DKX.html

## ⬜ 待确认 · onion-wine · 揭露红酒软化血管的营销骗局，资本和名校博士集体学术造假

https://www.bilibili.com/video/BV1Zm41117HJ（丧钟克里斯 · 144189 播放）

- **c1** 红酒含有的白藜芦醇不能软化血管
  - 原话：「白藜芦醇不仅没有保护心脏、抗衰老、软化血管的效果」
  - 标签：**正确**（correct）— 权威来源明确红酒白藜芦醇含量低，不能软化血管
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?id=7357433032954314752
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=BYQo
  - 出处：https://www.medtimes.com.hk/en-us/wikisingle-1311.html
- **c2** 白藜芦醇会导致严重的肾衰竭
  - 原话：「还会导致严重的肾衰竭」
  - 标签：**错误**（wrong）— 权威来源显示白藜芦醇改善肾功能、延缓肾衰竭，与说法矛盾
  - 出处：https://www.sinomed.ac.cn/article.do?ui=2025429816
  - 出处：https://pubmed.ncbi.nlm.nih.gov/32040471/#abstract#1
- **c3** 红酒中白藜芦醇含量最高也只有每毫升5.09微克
  - 原话：「也只有每毫升5.09微克」
  - 标签：**无法核实**（unverifiable）— 来源仅给总量范围，未提每毫升5.09微克上限
  - 出处：https://www.cnki.com.cn/Article/CJFDTotal-SPYK201422035.htm#1
  - 出处：https://www.spgykj.com/article/exportPdf?id=SPKJ201302008&st=alljournals#3#3
- **c4** 靠喝红酒达到软化血管效果需至少连喝两大瓶
  - 原话：「至少连喝两大瓶才行」
  - 标签：**错误**（wrong）— 权威来源称需每天喝上百瓶红酒才达实验剂量，且红酒不能软化血管
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=VMre
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?id=7357433032954314752

## ⬜ 待确认 · bp-drugs · 一片降压药为何能 24 小时平稳控压？看高清镜头下的释放过程

https://www.bilibili.com/video/BV1HsP5zTEcb（科普中国 · 92625 播放）

- **c1** 硝苯地平控释片只需每日服用一片
  - 原话：「只需每日服用一片」
  - 标签：**正确**（correct）— 说明书及权威来源均载明常规一日一次、一次一片
  - 出处：https://swin.zy91.com/pages/m-instruction/m.instruction.html?webHisId=15098&hospitalCode=1#1#2
  - 出处：https://www.lunan.com.cn/Product/Product/instruction/id/271.html
  - 出处：https://www.zdsfy.net/kpzs/109592.jhtml
- **c2** 硝苯地平控释片的半透膜包衣层在体内不会溶解
  - 原话：「半透膜包衣层在体内不会溶解」
  - 标签：**正确**（correct）— 多个权威来源明确半透膜外壳不溶解，随粪便排出
  - 出处：https://www.psmchina.cn/safe_medicines_information/safe_medicines_knowledge/jbcs/4322
  - 出处：https://wsjkw.gd.gov.cn/jkkp/kpzs/content/post_4882942.html
  - 出处：https://www.zxhospital.com/yxb/info/1024/5477.htm
- **c3** 大便中发现硝苯地平控释片的药壳是正常现象
  - 原话：「这是正常现象」
  - 标签：**正确**（correct）— 多个权威来源明确说明控释片空壳随粪便排出属正常现象
  - 出处：https://www.psmchina.cn/safe_medicines_information/safe_medicines_knowledge/jbcs/12526
  - 出处：https://www.psmchina.cn/safe_medicines_information/safe_medicines_knowledge/jbcs/4322
  - 出处：http://hbsyjd.cjyun.org/p/24646.html
- **c4** 硝苯地平控释片能实现药物稳定匀速释放
  - 原话：「药物的稳定匀速释放」
  - 标签：**正确**（correct）— 多个权威来源均明确硝苯地平控释片定时定量匀速释放
  - 出处：https://www.simcere.com/pro/detail.aspx?mtt=68
  - 出处：http://s.dayi.org.cn/mip/s/qa/43941_t.html
  - 出处：https://www.psmchina.cn/safe_medicines_information/safe_medicines_knowledge/jbcs/12526
  - 出处：https://www.pharnexcloud.com/zixun/sd_4311#1

## ⬜ 待确认 · grapefruit · 经常吃降压药的人，千万别碰这两种水果!

https://www.bilibili.com/video/BV1WXj86TEW7（陈大夫科普 · 2186471 播放）

- **c1** 吃降压药的人不能吃西柚及含西柚汁的饮料
  - 原话：「西柚，包括所有含西柚汁的饮料」
  - 标签：**部分正确**（partial）— 来源称部分降压药（如氨氯地平、非洛地平等）忌西柚，非所有降压药
  - 出处：http://health.cnr.cn/jkgdxw/20170704/t20170704_523832591.shtml#1
  - 出处：https://wsjkw.sh.gov.cn/jtyx/20210820/98c19357ce0943ab99bbeaa233c919ab.html
- **c2** 吃普利类、沙坦类或保钾利尿剂降压药的人要当心香蕉、橘子、土豆等高钾食物
  - 原话：「这些高钾食物留一万个心」
  - 标签：**正确**（correct）— 多个来源均指出普利类、沙坦类及保钾利尿剂减少钾排泄，需当心高钾食物
  - 出处：https://www.sinocare.com/en/sugerinfo_1_881.html
  - 出处：https://www.jy4yy.com/html/JianKang/202512/7Ux7Ku8Ji3Ud91530.html
  - 出处：https://ypk.39.net/saftydrugs/ao3e94p3.html
  - 出处：https://wsjkw.sh.gov.cn/jthl/20260211/6a855250b0f24794a715ca29b544b955.html
- **c3** 吃地平类降压药的人不用怕香蕉，医生有时还会鼓励适当吃一点
  - 原话：「不仅不用怕香蕉」
  - 标签：**部分正确**（partial）— 来源称地平类不影响血钾，香蕉适量可食，但未提医生鼓励
  - 出处：https://ypk.39.net/saftydrugs/omty01wb.html
  - 出处：https://m.dayi.org.cn/qa/327341.html#1
- **c4** 西柚中的成分会抑制肝脏代谢降压药，使药物浓度升高导致低血压
  - 原话：「浓度直接翻倍」
  - 标签：**正确**（correct）— 多个权威来源一致指出西柚抑制肝酶使降压药浓度升高致低血压
  - 出处：http://health-app.people.cn/n1/2025/1031/c14739-40593848.html
  - 出处：https://wsjkw.sh.gov.cn/jtyx/20210820/98c19357ce0943ab99bbeaa233c919ab.html
  - 出处：https://www.hnsyzszxyy.cn/jscgQJ/info_176.aspx?itemid=39986&subjectid=60&subcoumnid=8

## ⬜ 待确认 · morning-exercise · 坚持早起锻炼，你的身体会发生什么？

https://www.bilibili.com/video/BV11C41187TY（李白尼的猜想 · 4182999 播放）

- **c1** 坚持户外锻炼20到30分钟后，角质形成细胞会促使身体产生睾酮
  - 原话：「角质形成细胞开启了它的副业」
  - 标签：**无法核实**（unverifiable）— 来源未提及户外锻炼20-30分钟、角质形成细胞与睾酮关联
  - 出处：http://nrb.net.in/Books/heal-yourself-with-sunlight.pdf#20#13
  - 出处：https://www.pelleedintorni.it/ringiovanire-allenandosi/
  - 出处：https://www.nzherald.co.nz/northern-advocate/news/health-by-choice-exercise-offers-a-multitude-of-health-benefits/2AUMJ2T5OB7PAY6UZUXID4XR4U/?ref=readmore#1
  - 出处：https://www.nikkan-gendai.com/articles/view/health/350377/2
  - 出处：https://www.physio-pedia.com:443/index.php?title=Exercise_Endocrine_System_Interaction&diff=prev&oldid=313530
- **c2** 早上锻炼后减脂效果可能会更好
  - 原话：「你的减脂效果可能会更好」
  - 标签：**部分正确**（partial）— 多来源支持早上运动减脂更佳，但称效果可能更好属大体对，部分来源强调个体差异
  - 出处：https://www.womenshealthmag.com/tw/fitness/work-outs/a65589556/best-time-to-workout-to-lose-weight-1754301175/#1
  - 出处：https://health.ltn.com.tw/article/breakingnews/5195485?utm_campaign=STARK_health_DQN&utm_source=HEALTH&utm_medium=hotnews_right
  - 出处：https://www.sxmh.net.cn/article_detail/4156.html
  - 出处：https://dxy.com/article/202321#1
  - 出处：https://health.ftvnews.com.tw/news/detail/2025417W0216
- **c3** 阴天室外照度有1000到10000勒克斯，远高于室内100到500勒克斯
  - 原话：「阴天室外的照度也有1000到10000LX」
  - 标签：**部分正确**（partial）— 科普中国称阴天室外约20000lx，高于说法上限；室内数值来源不一，部分矛盾
  - 出处：https://www.kepuchina.cn/article/articleinfo?ar_id=518125&business_type=100#1
  - 出处：https://faithtech.cn/news/185
- **c4** 早上六点的低角度太阳光可深入大脑驱动视交叉上核，设定约16小时后入睡
  - 原话：「让你能在大约16小时后入睡」
  - 标签：**部分正确**（partial）— 来源支持晨光经眼调节视交叉上核，但未支持“深入大脑”及约16小时设定
  - 出处：http://big5.cctv.com/gate/big5/news.cctv.com/2025/08/28/ARTIMgovaq776Tgk5mGuAfR0250828.shtml
  - 出处：https://m.zhangyue.com/readbook/12896295/8.html#1
  - 出处：https://www.dzjkb.org.cn/dazhongkepu/dazhongkepu/f3eb933923292ab0ae7def0668de0526.html

## ⬜ 待确认 · sugar-free · 无糖饮料“可能”比有糖饮料危害更大？

https://www.bilibili.com/video/BV1aD4y167Wg（中国食品报融媒体 · 941064 播放）

- **c1** 无糖饮料确实不含糖，甜味来自阿斯巴甜、赤藓糖醇、三氯蔗糖等代糖
  - 原话：「无糖饮料确实没有糖这个物质」
  - 标签：**正确**（correct）— 央广网与科普中国均证实无糖饮料用阿斯巴甜、赤藓糖醇、三氯蔗糖等代糖提供甜味
  - 出处：http://health.cnr.cn/jkgdxw/20230320/t20230320_526187918.shtml#1
  - 出处：https://www.kepuchina.cn/health/food/202008/t20200806_1671955.shtml#1
- **c2** 阿斯巴甜即便在安全剂量下仍可能引起全身炎症
  - 原话：「即便是在安全剂量下仍然可能引起全身的炎症」
  - 标签：**部分正确**（partial）— 动物研究显示ADI剂量促炎，但人体全身炎症证据不足
  - 出处：https://ift.onlinelibrary.wiley.com/doi/10.1111/1750-3841.17505?af=R&content=articlesChapters&field1=Keyword&mi=66uo12o&target=default&text1=cytokines#1
  - 出处：https://rcseng.ovidds.com:443/discover/result?logSearchID=167467290&pubid=solr_6057-medline%3A39475342#1
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S0278691523003332?fr=pjs&ref=cra_js_challenge#1
- **c3** 毒理学报告不等于医学临床报告，得不出无糖饮料一定比含糖饮料危害大的结论
  - 原话：「毒理学报告不等于医学临床报告」
  - 标签：**正确**（correct）— 来源区分毒理学非临床研究与临床研究，支持二者不等同
  - 出处：https://www.isaf.gov.mo/wp-content/uploads/2025/11/%E5%8D%B0%E5%88%B7%E7%89%88-%E4%B8%AD%E6%88%90%E8%97%A5%E8%A8%BB%E5%86%8A%E6%8C%87%E5%BC%95-%E7%B0%A1%E8%91%A1-ver21.pdf#12#2
  - 出处：https://sage.cnpereading.com/paragraph/download/?doi=10.1177/10915818211073047#6#3
- **c4** 不论含糖还是无糖饮料都不应大量长期饮用，要适量
  - 原话：「都不应该大量长期饮用」
  - 标签：**正确**（correct）— 权威来源均提示饮料不宜替代水、过量饮用有健康风险
  - 出处：https://health.cnr.cn/jkgdxw/20260609/t20260609_527654236.shtml
  - 出处：http://health.cnr.cn/jkgdxw/20170824/t20170824_523915868.shtml
  - 出处：https://news.foodmate.net/2026/07/747338.html

## ⬜ 待确认 · supplements · 坐着抬一抬脚后跟，就能帮助降血糖和血脂，关键要做对，收藏转发

https://www.bilibili.com/video/BV1LKoXBEEEN（普外科曾伊森 · 113785 播放）

- **c1** 坚持做坐姿提踵可以降低血糖和血脂
  - 原话：「你坚持做坐姿提踵，那你就可以降低血糖血脂」
  - 标签：**部分正确**（partial）— 来源支持降餐后血糖，但血脂仅称“慢慢变好”，未明确降低血脂
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7463996506631540736
  - 出处：https://www.minhou.gov.cn/xjwz/zwgk/zdlyxxgk/jdjc/jbyfkz/202605/t20260518_5323132.htm
- **c2** 坐姿提踵能改善炎性指标
  - 原话：「它可以改善炎性指标」
  - 标签：**正确**（correct）— 科普中国、北京市政府等权威来源均称可显著降低全身免疫炎症指数
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7463996506631540736
  - 出处：https://www.beijing.gov.cn/gate/big5/www.beijing.gov.cn/fuwu/bmfw/sy/jrts/202606/t20260604_4685537.html
- **c3** 坐姿提踵主要激活小腿深层的比目鱼肌
  - 原话：「才是专门针对比目鱼肌的」
  - 标签：**正确**（correct）— 多个来源均指出坐姿提踵主要刺激深层比目鱼肌
  - 出处：https://tyj.sc.gov.cn/sctyj/jszd/2020/4/13/e3e0ae3b6ec249729fef03d11768797a.shtml
  - 出处：https://baike.baidu.com/planet/issue?issueId=583914
- **c4** 站姿提踵主要激活小腿表层腓肠肌，效果不如坐姿提踵
  - 原话：「效果就会差一些」
  - 标签：**部分正确**（partial）— 站姿练腓肠肌有据，但“效果不如坐姿”来源未比较
  - 出处：https://baike.baidu.com/item/%e6%8f%90%e8%b8%b5/0?fromModule=lemma_inlink&bst=1791613192.d2baa81a317fb2cd#1
  - 出处：https://www.sport.gov.cn/n20001280/n20001265/n20066978/c25921683/content.html

## ⬜ 待确认 · iv-drip · 【花小烙】输液的时候如果气泡进入了血管里会怎么样？

https://www.bilibili.com/video/BV1GB4y1D7cK（画渣花小烙 · 15429673 播放）

- **c1** 少量小气泡进入血管会溶进血液或被身体吸收，不会造成大的伤害
  - 原话：「不必特别担心」
  - 标签：**正确**（correct）— 科普中国等权威来源称微量小气泡可被吸收代谢，不造成危害
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?id=7268714124975124480
  - 出处：http://www.jksb.com.cn/index.php?m=wap&a=show&catid=277&id=117646
  - 出处：http://www.yxhospital.cn/c/2022/04/07/17709.shtml
- **c2** 对成年人来说致命的空气栓塞量在200到300毫升左右
  - 原话：「在200到300毫升左右」
  - 标签：**部分正确**（partial）— 来源称约3–5ml/kg，60kg成人180–300ml，需快速输入；说法遗漏体重与速度条件
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7410774562299162624#1
  - 出处：https://www.elsevier.es/en-revista-spanish-journal-legal-medicine-446-articulo-iatrogenic-gas-embolism-S2445424923000250
- **c3** 输液时瓶内液体输完，身体血压不允许空气大量进入，最多回一些血
  - 原话：「最多也就是回一些血出来而已」
  - 标签：**正确**（correct）— 科普中国等来源均称静脉压高于大气压，空气不易进入，最多回血
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7110411945885544448#1
  - 出处：http://www.scmy120.com/nrgl/show-5132.html
  - 出处：https://hosp.ccnu.edu.cn/info/1124/3561.htm#1
  - 出处：https://www.xtsyyy.com/HTML/2021/2/1358.shtml
- **c4** 大量空气进入血管会堵住肺部血管分支，导致呼吸困难等缺氧症状
  - 原话：「呼吸困难」
  - 标签：**部分正确**（partial）— 来源称静脉气体栓塞可致肺水肿/窒息，但未明确说堵住肺部血管分支
  - 出处：https://www.msdmanuals.cn/professional/injuries-poisoning/injury-during-diving-or-work-in-compressed-air/arterial-gas-embolism?media=full%3Fwautoredirectid%3D17#mainContainer#1

## ⬜ 待确认 · black-sesame · 重磅研究！哈佛大学学者白发研究刊登《Nature》，压力竟会导致体内这种细胞被耗尽【笔百科·白头发】

https://www.bilibili.com/video/BV1tX4y1R7Cf（蜡笔和小勋 · 1633918 播放）

- **c1** 精神压力可能导致头发迅速变白
  - 原话：「精神压力可能会导致头发迅速变白」
  - 标签：**部分正确**（partial）— 来源承认压力可致白发，但强调不会一夜全白，说法略夸大
  - 出处：http://jiankang.cctv.com/2021/12/24/ARTIgkwWZ0dXSxqTZ68bRlrV211224.shtml
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=YAVY
  - 出处：https://health.cnr.cn/jkgdxw/20240816/t20240816_526854515.shtml
- **c2** 压力导致的白发几乎不可逆
  - 原话：「几乎是不可逆的」
  - 标签：**错误**（wrong）— 权威来源称压力减轻后部分白发可恢复原发色，与不可逆矛盾
  - 出处：https://ypjgj.qinghai.gov.cn/Article/FormDetailsYJJ?Article_ID=B1EAA371-D2BF-4771-B00C-DDC9BFA4A6BA#1
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7476461553966440448
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?from=1&id=7426354028138074112&is_self=2
- **c3** 头发白不白和身体健康程度没有必然联系
  - 原话：「没有必然的联系」
  - 标签：**正确**（correct）— 权威来源明确称白发多少与健康无直接关系
  - 出处：http://health.cnr.cn/jkgdxw/20170609/t20170609_523793434.shtml
  - 出处：http://www.pumcderm.net/list/97/4894.html
- **c4** 通常烫发比染发对头发的伤害更大
  - 原话：「烫发比染发对头发的伤害要更大」
  - 标签：**无法核实**（unverifiable）— 来源仅讨论烫染价格差异及染发损伤，未比较烫发与染发伤害大小
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?id=6970466922933821440#1
  - 出处：https://www.kepuchina.cn/article/articleinfo?ar_id=89972&business_type=100&classify=0#1
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7014675981516210176

## ⬜ 待确认 · breakfast · 【医学博士】不吃早饭会得胃炎吗？为什么你一饿就胃疼？｜如何科学养胃？

https://www.bilibili.com/video/BV1YPcrzREe6（兔叭咯 · 1793672 播放）

- **c1** 空腹时间过长会引发胃炎
  - 原话：「空腹时间过长确实会得胃炎」
  - 标签：**正确**（correct）— 多个权威来源指出长期空腹胃酸刺激胃黏膜可致胃炎
  - 出处：http://www.ncrc-dd.org.cn/Html/News/Articles/4730.html
  - 出处：https://health.rednet.cn/content/646048/50/15846091.html
  - 出处：https://jbk.39.net/mxwy/230915/d4f9umm.html
- **c2** 生理性空腹超过15小时会增加健康风险
  - 原话：「生理性空腹超过15个小时会增加健康风险」
  - 标签：**部分正确**（partial）— 来源提及空腹超12小时增胆结石风险，未直接支持15小时阈值
  - 出处：https://health.udn.com/health/story/5999/8901858?from=udn-articlemain_ch1005
  - 出处：https://mejorconsalud.as.com/salud/cuerpo-humano/consecuencias-no-comer-varias-horas/#1
- **c3** 服用铋剂后大便变黑属于正常现象
  - 原话：「铋剂吃完了确实粑粑会变成黑色的」
  - 标签：**正确**（correct）— 多个权威来源均指出服铋剂致黑便属正常现象
  - 出处：https://m.dayi.org.cn/qa/286301.html
  - 出处：https://www.psmchina.cn/safe_medicines_information/safe_medicines_knowledge/jbcs/5204
  - 出处：https://www.psmchina.cn/safe_medicines_information/safe_medicines_knowledge/jbcs/9762
- **c4** 吃饭太快会导致血糖快速升高并可能引起胰岛素抵抗
  - 原话：「吃快了吃多了血糖会顶格地高」
  - 标签：**部分正确**（partial）— 有来源支持吃饭快与胰岛素抵抗相关，但血糖快速升高的说法被Wiley研究否定
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S009174350700326X?via=ihub#1
  - 出处：https://onlinelibrary.wiley.com/doi/full/10.1002/edm2.56#1

## ⬜ 待确认 · eight-glasses · 如果你每天喝一加仑3.8升水身体会怎样？

https://www.bilibili.com/video/BV1jCPzzwEFo（powerrrrr123 · 503275 播放）

- **c1** 每天喝一加仑水，第一周肾脏会适应并像高性能机器一样过滤
  - 原话：「你的肾脏适应了」
  - 标签：**无法核实**（unverifiable）— 来源仅泛述饮水益处或个案体验，未证实肾脏第一周适应并高效过滤
  - 出处：https://pkdcure.org/wp-content/uploads/2024/11/cooking_well_2021-edit.pdf#12#2
  - 出处：https://kidney.org.au/wp-content/uploads/2025/10/KHA-Factsheet-Drink-Water-Instead-2025.pdf#1#1
  - 出处：https://www.ettoday.net/news/20170406/898772.htm?ercamp=hot_news
  - 出处：https://m.huanqiu.com/article/9CaKrnK1NMv
  - 出处：https://read.qxmd.com/read/42886618/fluid-intake-and-kidney-function-a-systematic-review-and-dose-response-meta-analysis
- **c2** 每天喝一加仑水到第30天关节更顺滑、膝盖咔咔声消失
  - 原话：「膝盖的咔咔声？消失了」
  - 标签：**无法核实**（unverifiable）— 来源仅泛谈关节响与润滑，未涉及每日一加仑水30天效果
  - 出处：https://www.kingnet.com.tw/inquiry/single?accessKey=8c43a951fa4696201d115cb347a978a5&inquiryId=84819#1
  - 出处：https://news.cts.com.tw/cts/life/201912/201912171984536.html
  - 出处：https://health.tvbs.com.tw/regimen/342118?from=readmore
  - 出处：https://pansci.asia/archives/70817/amp#1
- **c3** 每天喝一加仑水到第60天新陈代谢加快、更有效燃烧卡路里
  - 原话：「新陈代谢运行得更快」
  - 标签：**错误**（wrong）— 来源显示饮水产热效应有限且短暂，无证据支持每天一加仑60天持续加快代谢
  - 出处：https://pubmed.ncbi.nlm.nih.gov/14671205/#1
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=Zynv
  - 出处：https://www.nature.com/articles/nutd201541#1
- **c4** 每天喝一加仑水到第90天看起来年轻五岁
  - 原话：「你看起来年轻了五岁」
  - 标签：**错误**（wrong）— 来源均为每天3升水4周个案，非一加仑90天年轻五岁
  - 出处：https://my.top1health.com/Article/232/94013

## ⬜ 待确认 · vitamin-c · 【医学博士】感冒吃药7天好，不吃药一星期好 | 身体：你在考我数学？

https://www.bilibili.com/video/BV1ha4y1s7qd（兔叭咯 · 2002403 播放）

- **c1** 感冒大部分是由病毒引起的
  - 原话：「感冒大部分是由病毒引起」
  - 标签：**正确**（correct）— 权威来源明确感冒为病毒感染，多数由鼻病毒等引起
  - 出处：https://ccdas.pmphai.com/appdisease/toPcDetail?sessionId=&knowledgeLibPrefix=disease&id=29240#1
  - 出处：http://www.msdmanuals.cn/professional/infectious-diseases/respiratory-viruses/common-cold?media=full?wruleredirectid=3?wautoredirectid=36589#1
  - 出处：http://health.cnr.cn/jkgdxw/20240115/t20240115_526558121.shtml
- **c2** 感冒不吃药7天就能好
  - 原话：「感冒不吃药7天就能好」
  - 标签：**正确**（correct）— 多个权威来源称普通感冒自限，约7天自愈，无需药物
  - 出处：https://wsjkw.sh.gov.cn/jthl/20240814/36d4212387344c9890666e47ffea4eeb.html#1#1
  - 出处：https://www.shgh.cn/Content/News/4171
  - 出处：https://uhs.berkeley.edu/health-promotion/health-topics/colds-and-respiratory-infections/cold-care#1
  - 出处：https://www.nejm.org/doi/pdf/10.1056/NEJM198601093140209
  - 出处：http://wjw.hunan.gov.cn/xxgk/gzdt/szdt/202211/t20221103_29114473.html
- **c3** 母乳中的乳铁蛋白可以刺激婴儿T细胞增殖
  - 原话：「乳铁蛋白可以刺激小小兔T细胞的增值」
  - 标签：**部分正确**（partial）— 有来源显示乳铁蛋白刺激胸腺细胞，但另有来源显示抑制T细胞增殖，说法不全面
  - 出处：https://pubmed.ncbi.nlm.nih.gov/1683650/#1
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/0165037887900416#1
- **c4** 建议每天睡眠7到9个小时
  - 原话：「建议每天睡眠7-9个小时」
  - 标签：**部分正确**（partial）— 部分来源支持7-9小时，但权威指南多称成人7-8小时
  - 出处：https://cdcp.gd.gov.cn/zwgk/jsbzywj/content/mpost_4697833.html#1
  - 出处：https://wsjkw.sc.gov.cn/scwsjkw/jkys/2025/3/31/da44e475de514fbe8e8148cd1f8c74a2.shtml
  - 出处：https://www.pkuh6.cn/Html/Mobile/Articles/6185.html

## ⬜ 待确认 · ejiao · 为什么阿胶在西医上并无营养只是一些蛋白质，而在中医上则是补品？

https://www.bilibili.com/video/BV1C8411U7Hi（今夜话题ing · 362465 播放）

- **c1** 阿胶营养密度高，70%以上是蛋白质
  - 原话：「营养密度高70%以上是蛋白质」
  - 标签：**部分正确**（partial）— 权威来源显示蛋白质68%-84%，但阿胶片阿胶含量39%-65%，营养密度说法需限定
  - 出处：https://www.sinomed.ac.cn/article.do?ui=2019209309
  - 出处：https://m.meishichina.com/ingredient/EJiao/info/
- **c2** 阿胶在常温条件下可以多年不腐
  - 原话：「常温条件下可以多年不腐」
  - 标签：**部分正确**（partial）— 来源称保存得当可5年或更久，但未支持常温多年不腐，且强调防潮防霉
  - 出处：https://ypk.39.net/saftydrugs/37smu5uz.html
  - 出处：https://h5.baike.qq.com/mobile/search_article.html?docid=qa000020119lgnaa&adtag=sg.nr.wz.wenda&VNK=acab5920
  - 出处：http://www.edongeejiao.com/fk_f1/Index_74.aspx
- **c3** 坐月子不能洗澡是落后观念
  - 原话：「我们现在都知道是落后观念」
  - 标签：**正确**（correct）— 多个权威来源均指出不能洗澡是旧观念，现代可科学洗浴
  - 出处：http://health.cnr.cn/jkgdxw/20170724/t20170724_523865146.shtml
  - 出处：http://jiankang.cctv.com/m/index.shtml?article_id=ARTIn6z5o73bPM9H7DidkY91170807
  - 出处：https://wsjkw.sh.gov.cn/ycfbj/20210716/8f251fe00c7f41759ff63857b13eb868.html
  - 出处：https://www.hpa.gov.tw/Pages/Detail.aspx?nodeid=127&pid=8103
  - 出处：http://health.cnr.cn/jkgdxw/20190626/t20190626_524663927.shtml
- **c4** 金创药对创面止血有效
  - 原话：「所以对创面止血有效」
  - 标签：**正确**（correct）— 北京卫健委科普称金创药外敷可止血，与说法一致
  - 出处：https://wjw.beijing.gov.cn/bmfw_20143/jkzs/jksh/202502/t20250220_4015504.html#1

## ⬜ 待确认 · fish-oil · 鱼油不如蛙跳——以10篇论文佐证

https://www.bilibili.com/video/BV1KzoKBgEXz（耿同学讲故事 · 1187596 播放）

- **c1** 每天补充4克Omega-3脂肪酸对心血管不良事件没有显著差异
  - 原话：「没有显著差异」
  - 标签：**无法核实**（unverifiable）— 来源为试验注册与综述表格，未提供4克剂量对心血管事件无差异的结论
  - 出处：https://ichgcp.net/clinical-trials-registry/NCT06840964#1
  - 出处：https://en.irct.ir/trial/92646
  - 出处：https://link.springer.com/article/10.1007/s11883-025-01363-2/tables/1#1
- **c2** 补充Omega-3脂肪酸不会降低重大心血管事件或癌症的发生率
  - 原话：「不会导致重大心血管事件或癌症」
  - 标签：**无法核实**（unverifiable）— 来源均为试验注册或特定癌症研究，未提供心血管事件与癌症发生率结论
  - 出处：https://clinicaltrials.gov/study/NCT06195306?term=Tamoxifen%20AND%20ESR1&viewType=Table&rank=6#1
  - 出处：https://clinicaltrials.gov/study/NCT02295059?intr=Omega-3%20Fatty%20Acids&tab=researcher#1
  - 出处：https://ods.od.nih.gov/FACTSHEETS/OMEGA3FATTYACIDS-HEALTHPROFESSIONAL/?print=1#7
  - 出处：https://www.michiganmedicine.org/health-lab/fish-oil-supplements-may-not-work-certain-cancer-patients
  - 出处：https://drks.de/search/de/trial/DRKS00036800/details
- **c3** 鱼油补充剂对超重男性肝脏脂肪无效
  - 原话：「对肝脏脂肪的影响 无效」
  - 标签：**错误**（wrong）— 来源显示鱼油可减少肝脂肪，与说法矛盾
  - 出处：https://healthcare-service.amed.go.jp/assets/document/guide/video/guide_video_11.pdf#22#4
  - 出处：https://clinicaltrials.gov/study/NCT00230113?tab=researcher#1
- **c4** 补充Omega-3对炎症细胞因子水平没有影响
  - 原话：「炎症细胞因子水平都没有影响」
  - 标签：**错误**（wrong）— 多项权威来源显示Omega-3降低TNF-α、IL-1等炎症因子，与说法矛盾
  - 出处：https://europepmc.org/article/MED/39286404#free-full-text#2
  - 出处：https://www.nejm.org/doi/abs/10.1056/NEJM198902023200501#1
  - 出处：https://secure.jbs.elsevierhealth.com/action/getSharedSiteSession?redirect=https%3A%2F%2Fajcn.nutrition.org%2Farticle%2FS0002-9165%2822%2903903-X%2Fpdf&rc=0&__cf_chl_tk=i1iWosfmCBF.4uvY.KMwxyUhiWKlsY_IUS7mhK6kmJg-1769524094-1.0.1.1-dH8PtswazsvQOzA.0FcH7v3DIxGlnoptQP7IVWe9fhs#5#5

## ⬜ 待确认 · whole-grains · 【万物由来】粗粮细粮，你分得清吗？

https://www.bilibili.com/video/BV1kh411k7qu（马督工 · 224102 播放）

- **c1** 粗粮和细粮的分界线是加工精度
  - 原话：「真正的分界线是加工精度」
  - 标签：**正确**（correct）— 科普中国指出大米因碾磨加工精度不同可为粗粮或细粮
  - 出处：https://www.kepuchina.cn/1/15/201703/t20170301_113026.shtml
- **c2** 细粮GI值高，会快速升高血糖
  - 原话：「细粮的GI值高」
  - 标签：**正确**（correct）— 权威来源明确细粮GI高，进食后血糖升高较快
  - 出处：https://www.chinanutri.cn/yyj/wxpt/201603/t20160318_126278.html
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=6967609978615046144
- **c3** 粗粮富含纤维素，消化慢，GI值低
  - 原话：「粗粮富含纤维素」
  - 标签：**部分正确**（partial）— 权威来源称粗粮等属低GI，但指出并非所有粗粮都低GI，糯性粗粮升糖快
  - 出处：https://www.gzscdc.org.cn/ggfw/jkjy/kpxc/yyws/content_6559
  - 出处：https://ezszxyy.com/index.php/jkkp/2025/08-20/4255.html
- **c4** 燕麦是粗粮中维生素和叶酸含量最高的品种
  - 原话：「维生素和叶酸含量最高的品种是燕麦」
  - 标签：**无法核实**（unverifiable）— 来源仅称燕麦叶酸较高，未比较所有粗粮，无法支持最高
  - 出处：https://www.cnzcs.com/maternal/Pregnant/Preg_list_detail.aspx?id=6932
  - 出处：https://www.spkx.net.cn/CN/abstract/abstract35272.shtml?st=aipub#1

## ⬜ 待确认 · salt-bp · 为家里长辈多花几块钱，换种盐就能控血压（有前提的那种

https://www.bilibili.com/video/BV1HL4y1H7QN（丁香医生 · 349170 播放）

- **c1** 老年人吃菜越来越咸可能是因为味觉敏感度下降
  - 原话：「很可能是因为老人家味觉敏感度下降」
  - 标签：**正确**（correct）— 默沙东诊疗手册指出老年人味觉敏感度下降，尤其咸味感知下降
  - 出处：https://www.msdmanuals.cn/home/multimedia/table/spotlight-on-aging
- **c2** 高盐饮食会带来高风险的心血管疾病
  - 原话：「高盐饮食带来的很有可能是高风险的心血管疾病」
  - 标签：**正确**（correct）— 多个权威来源一致指出高盐/高钠摄入增加心血管疾病风险
  - 出处：https://journals.lww.com/md-journal/fulltext/2025/03140/association_of_salt_added_to_food_with_risk_of.39.aspx#1
  - 出处：https://wsjkw.gxzf.gov.cn/xxgk_49493/fdzdgk/ggws/jkkp/yfzs/t26163544.shtml
  - 出处：http://health-app.people.cn/n1/2020/0804/c14739-31809542.html#1
  - 出处：https://www.jacc.org/doi/pdf/10.1016/j.jacc.2012.08.998#1#1
- **c3** 把家里的盐换成低钠盐可以降低血压和心血管疾病风险
  - 原话：「只要把盐换成了低钠盐 血压下降了」
  - 标签：**正确**（correct）— 多个权威来源一致支持低钠盐可降血压及心血管风险
  - 出处：https://health.cnr.cn/jkgdxw/20260502/t20260502_527607978.shtml#1
  - 出处：https://wsjkw.sc.gov.cn/scwsjkw/jkys/2022/3/1/3445f9df3c3b49d29d3b2a6fed1c9e36.shtml
  - 出处：https://jiankang.cctv.com/2025/02/26/ARTI2jeJp46sbyqI3Wgme29H250225.shtml
- **c4** 肾功能异常或正在服用影响钾排出药物的人不适合吃低钠盐
  - 原话：「低钠盐就可能不适合你们」
  - 标签：**正确**（correct）— 多个权威来源明确肾功能异常及服影响钾排出药物者不宜低钠盐
  - 出处：https://wsjkw.sh.gov.cn/ycfbj/20230614/70d9811324cd4be0818f5b1390ed42c8.html
  - 出处：http://sklcvd.fuwaihospital.org/News/Articles/Index/204260
  - 出处：http://jiankang.cctv.com/2016/04/12/ARTIX6KL1L47qkQTdG5vx9Pb160412.shtml
  - 出处：https://jxt.zj.gov.cn/art/2025/10/16/art_1229123455_5661194.html

## ⬜ 待确认 · honey-cough · 【花小烙】感冒好了之后为什么总是咳嗽很久？

https://www.bilibili.com/video/BV1n64y1A7C1（画渣花小烙 · 4132742 播放）

- **c1** 咳嗽本身是一种自我保护机制
  - 原话：「咳嗽本身是一种自我保护机制」
  - 标签：**正确**（correct）— 多个权威来源明确称咳嗽是自我保护性反射/防御机制
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=DLMd
  - 出处：https://www.zgkpw.org.cn/newspaper/content_251336.html
- **c2** 感冒好了以后仍可能持续咳嗽很久
  - 原话：「感冒都好了还会咳嗽很久」
  - 标签：**正确**（correct）— 多个权威来源均指出感冒后咳嗽可持续3-8周
  - 出处：http://health.cnr.cn/sygd/20241121/t20241121_526983846.shtml
  - 出处：https://www.sxcdc.cn/zxzx/spbd/art/2025/art_fd96d051f86340cab8b3011d0684a94f.html
- **c3** 咳嗽持续太久并伴有喘息、呼吸困难时应及时到医院就诊
  - 原话：「伴有喘息 呼吸困难」
  - 标签：**正确**（correct）— 权威来源指出呼吸困难/喘息需立即就医，与说法一致
  - 出处：https://www.healthychildren.org/English/tips-tools/Symptom-Checker/IFrame/Pages/symptomviewer.aspx?symptom=Breathing+Trouble&_gl=1*dbngd5*_ga*MTIxODQzODcxNS4xNzYxMDY2MDkx*_ga_FD9D3XZVQQ*czE3NzAxMzg4MzYkbzgkZzEkdDE3NzAxMzk2NTEkajU0JGwwJGgw&gad_source=1&gbraid=0AAAAAqMzUp-WPp8w4-2MGQbDE4C77068N&gclid=Cj0KCQjwzYLABhD4ARIsALySuCT1zL8zavqwq6Y-1ZPDTTSZsDCurbF-sjIKgFYLqjg_pKnw3gqro3waAn65EALw_wcB#1
  - 出处：https://www.scmc.com.cn/list/1360/5350.html
- **c4** 气道高反应性是持续咳嗽的重要原因之一
  - 原话：「气道高反应性」
  - 标签：**正确**（correct）— 多项权威来源均将气道高反应性与慢性咳嗽关联研究
  - 出处：https://www.uptodate.com/contents/approach-to-chronic-cough-in-children/abstract/53
  - 出处：https://www.sinomed.ac.cn/article.do?ui=2023339046
  - 出处：https://read.cnki.net/web/Conference/Article/ZGZP200904001117.html

## ⬜ 待确认 · sun-calcium · 为什么你年纪轻轻，也需要补钙？

https://www.bilibili.com/video/BV1GQ4y187yG（锦鲤实验室 · 474289 播放）

- **c1** 缺钙是让骨头提前达到退休年龄的原因
  - 原话：「让你的骨头先达到退休年龄的原因，就是缺钙」
  - 标签：**部分正确**（partial）— 来源称缺钙可致骨质疏松，但未提“骨头提前退休”的比喻，表述夸大
  - 出处：https://www.cma.org.cn/art/2023/6/14/art_4584_51318.html#1
  - 出处：http://s.dayi.org.cn/mip/s/disease/1157322.html?s_from=sgh_recom#1
- **c2** 大骨汤中能溶解的钙微乎其微
  - 原话：「骨汤中能溶解的钙微乎其微」
  - 标签：**正确**（correct）— 多个权威来源均指出大骨汤钙溶出极少，与说法一致
  - 出处：https://210.241.78.32/Pages/Detail.aspx?nodeid=1425&pid=8447
  - 出处：https://210.241.78.32/Pages/Detail.aspx?nodeid=127&pid=8752
  - 出处：https://piyao.kepuchina.cn/rumor/rumordetail?id=eegb
- **c3** 菠菜的钙吸收率只有5%，不适合作为补钙食物
  - 原话：「菠菜的钙吸收率只有5%」
  - 标签：**无法核实**（unverifiable）— 来源摘要未给出5%具体数值，无法核实
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S0002916523165099?via%3Dihub#1
  - 出处：https://https-pubmed-ncbi-nlm-nih-gov-443.webvpn.ynu.edu.cn/3354496/#1
  - 出处：https://dev.europepmc.org/article/MED/3354496
- **c4** 碳酸钙需经胃酸分解，一般应在用餐或饭后服用
  - 原话：「需要经过胃酸分解才能释放出钙离子」
  - 标签：**正确**（correct）— Mayo Clinic及说明书均称碳酸钙需随餐/饭后服，胃酸助吸收
  - 出处：https://www.mayoclinic.org/zh-hans/healthy-lifestyle/nutrition-and-healthy-eating/expert-answers/calcium-supplements/faq-20058238
  - 出处：https://swin.zy91.com/pages/m-instruction/m.instruction.html?webHisId=34493&hospitalCode=1

## ⬜ 待确认 · ginger-hair · 【医学博士】都2025年了，防脱洗发水还在卖？｜洗头越多，头发会越少？｜传说中的米诺地尔真的好使吗？｜资深雄脱是如何逆转脱发的！

https://www.bilibili.com/video/BV1KCMgzVEe9（兔叭咯 · 1992696 播放）

- **c1** 雄激素性脱发应直接使用米诺地尔，不必考虑洗发水。
  - 原话：「那就别考虑洗发水了，直接上米诺地尔吧」
  - 标签：**部分正确**（partial）— 来源支持米诺地尔治疗雄脱，但未说无需考虑洗发水，说法绝对化
  - 出处：https://m.dayi.org.cn/qa/48219?from=sg#1
  - 出处：https://www.mayoclinic.org/zh-hans/diseases-conditions/hair-loss/diagnosis-treatment/drc-20372932?p=1#1#1#1
- **c2** 二氨基嘧啶氧化物与米诺地尔分子结构相似，能刺激毛囊细胞。
  - 原话：「它与米诺地尔的分子结构极为相似」
  - 标签：**部分正确**（partial）— 来源证实结构相似，但刺激毛囊细胞机制未明确支持
  - 出处：https://publish.cnki.net/journal/portal/xlxj/client/paper/664e0d3d0f11af62c8b9cc00ab6ebb31
  - 出处：https://www.ulprospector.com/zh-tw/eu/PersonalCare/Detail/33934/10834325/LOWENOL-AHL-N?st=20&sl=538197680&crit=SW50ZXJuZXQgU2VhcmNoID4g6Zuc55Kw5YyW5ZCI54mpID4g55u055m85YqR&ss=2&surl=aHR0cHM6Ly93d3cudWxwcm9zcGVjdG9yLmNvbS96aC10dy9ldS9QZXJzb25hbENhcmUvUHJvZHVjdHMvMzY5Ni9GdW5jdGlvbmFsaXRpZXMvNzIwNQ%3d%3d
- **c3** 选择洗发水应避免月桂醇硫酸酯钠等强清洁力成分，以免破坏毛囊。
  - 原话：「那种猛猛的清洁剂」
  - 标签：**部分正确**（partial）— 来源称SLS强清洁可伤屏障，但健康头皮通常耐受，非绝对避免
  - 出处：https://jbk.39.net/tf1/231009/d8hkppa.html
  - 出处：https://jbk.39.net/tf1/231228/a3l92c7.html
- **c4** 洗头时应用手指肚轻柔清洗，避免用指甲抠抓。
  - 原话：「用手指肚去洗头」
  - 标签：**正确**（correct）— 权威来源明确建议用指腹而非指甲洗头
  - 出处：https://health.tvbs.com.tw/regimen/354515?utm_source=linetoday&utm_medium=line_original

## ⬜ 待确认 · bp-drop-bad · 高血压患者吃降压药，血压降是坏事、降不下来才是好事！

https://www.bilibili.com/video/BV1PN411b7Bw（0 播放）

- **c1** 吃降压药后血压降不下来是好事
  - 原话：「降不下来就对了」
  - 标签：**错误**（wrong）— 权威来源均将服药后血压降不下来视为需处理的问题，而非好事
  - 出处：https://www.commonhealth.com.tw/article/94687?spchannel=ewm#1
  - 出处：https://hbmahospital.com/shownews/id/443
  - 出处：https://wsjkw.sh.gov.cn/xnxgjb/20240606/600fa780106d4fa2981049fea5149b92.html
- **c2** 血压高一点好，因为身体需要高血流速度
  - 原话：「血压高一点好」
  - 标签：**错误**（wrong）— 权威来源指出血压与心血管风险正相关，升高增加风险，非越高越好
  - 出处：https://www.bjcdc.org/cdcmodule/jkzt/jkts/2026/118573.shtml
  - 出处：https://www.dzjkb.org.cn/dazhongkepu/dazhongkepu/7956bf64e111862e7d5df6604a5079d5.html
- **c3** 吃降压药把血压降到120/80会让人难受
  - 原话：「到120/80他就难受」
  - 标签：**部分正确**（partial）— 央视来源称特定患者降120/80不适，但非普遍
  - 出处：http://jiankang.cctv.com/2018/05/08/ARTIRD40pZFML6YpQ8sa9zcp180508.shtml
- **c4** 硬把体温降下来一定是坏事
  - 原话：「硬降下体温来一定是坏事」
  - 标签：**部分正确**（partial）— 来源称盲目/强制退烧不利，但高热需退烧，说法绝对化
  - 出处：http://health.cnr.cn/jkgdxw/20170116/t20170116_523486610.shtml#1
  - 出处：http://health.nen.com.cn/network/health/dtrd/2026/08/04/939105609209353451.shtml
  - 出处：https://zjsfybjy.zhuji.gov.cn/art/2020/8/7/art_2465_915.html

## ⬜ 待确认 · tea-vessels · 两味药当茶喝，冲开血管，清理全身淤堵，让您全身轻松

https://www.bilibili.com/video/BV16u411N75c（0 播放）

- **c1** 丹参对血脂和动脉粥样硬化斑块有良好的治疗作用
  - 原话：「对血脂和动脉粥样硬化斑块等等都有良好的治疗作用」
  - 标签：**部分正确**（partial）— 动物实验显示丹参改善血脂和斑块，但非临床治疗证据
  - 出处：https://coaa.istic.ac.cn/openJournal/periodicalArticle/0120231100694544
  - 出处：https://www.cnki.com.cn/Article/CJFDTotal-ZLXZ200703020.htm#1
  - 出处：https://en.whuhzzs.com/data/article/lcxxg/preview/pdf/lcxxgbzz-42-4-272.pdf#2#1
  - 出处：https://med.wanfangdata.com.cn/Paper/Detail?id=PeriodicalPaper_zxyjh200504015&dbid=WF_QK
- **c2** 路路通具有祛风通络、利水消肿的功效
  - 原话：「它具有祛风通络利水消肿的功效」
  - 标签：**正确**（correct）— 多个来源均载祛风通络、利水（除湿/通经）功效
  - 出处：https://health.ltn.com.tw/article/breakingnews/4374695
  - 出处：http://adminc.yywsb.com/article/14503.html
  - 出处：https://www.dhzyy.cn/news_1/820.html
  - 出处：https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLDetailPrint.aspx?LicewordID=01&LiceNUM=057519
- **c3** 丹参和路路通一起煮水喝能清理血管壁上的垃圾
  - 原话：「清理血管壁上的垃圾」
  - 标签：**无法核实**（unverifiable）— 来源仅提丹参路路通活血祛瘀，未证实煮水清血管垃圾
  - 出处：https://patentimages.storage.googleapis.com/ff/c1/ae/9f3d7a19223dc0/CN107334834A.pdf#1#1
  - 出处：http://www.sjzyyzz.com/sjzyy/ch/reader/create_pdf.aspx?file_no=190620&year_id=2019&quarter_id=06&falg=1#3#3
  - 出处：https://gy120.cn/dangshow.asp?articleid=2432
- **c4** 丹参和路路通煮水喝能降低心脑血管疾病发生的风险
  - 原话：「自然就降低了心脑血管疾病发生的风险」
  - 标签：**部分正确**（partial）— 来源仅显示丹参路路通用于治疗心血管病，未证实煮水可降低发病风险
  - 出处：https://patentimages.storage.googleapis.com/ff/c1/ae/9f3d7a19223dc0/CN107334834A.pdf#1#1
  - 出处：https://wap-cnki-net-443.webvpn.imac.edu.cn/touch/web/Journal/Article/ZXJH201518046.html

## ⬜ 待确认 · clot-drink · 每天一杯溶栓液，祛除体内血管淤积，让您一身轻松

https://www.bilibili.com/video/BV1Pr4y197c9（0 播放）

- **c1** 桃仁、红花、赤芍、丹参等中药煮水喝能溶解血管里的斑块、打通血管淤堵
  - 原话：「溶解血管里的淤积的斑块」
  - 标签：**错误**（wrong）— 权威来源明确否认中药煮水能溶解斑块、疏通血管
  - 出处：https://jbk.39.net/gxb/240731/b5qqehm.html
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?from=1&id=7408944048344903680&is_self=2
- **c2** 这个溶栓汤液不能多喝，多喝会因药物过量导致身体不适应
  - 原话：「一定不要多喝，因为药物过量」
  - 标签：**部分正确**（partial）— 来源指出中药泡水非溶栓手段，过量有风险，但未直接评“溶栓汤液”
  - 出处：https://jbk.39.net/nxs/240720/q8q7vlk.html
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?from=1&id=7408944048344903680&is_self=2
  - 出处：https://ypk.39.net/saftydrugs/7lh7qmg5.html
- **c3** 坚持服用这个方子一周或一段时间就能见效
  - 原话：「坚持服用一周或者一段时间」
  - 标签：**部分正确**（partial）— 来源显示部分方药可一周见效，但强调辨证准确，非普遍保证
  - 出处：https://hnzhy.com/m/jkkp/zfnzz/1211289980297216.html
  - 出处：https://www.91160.com/doctors/askdetail/docid-200157821/askid-144033761.html
  - 出处：https://www.91160.com/doctors/articledetail/docid-1452/articleid-95857.html

## ⬜ 待确认 · anticancer-food · 抗癌食物第一名，肿瘤细胞，慢慢减少

https://www.bilibili.com/video/BV1Fc411871U（0 播放）

- **c1** 马齿苋含有硒元素和维生素E，具有抗癌物质
  - 原话：「它含有两种以上的抗癌的物质」
  - 标签：**部分正确**（partial）— 来源证实马齿苋有抗肿瘤活性，但未提及硒和维生素E，且抗癌物质表述夸大
  - 出处：https://www.sinomed.ac.cn/article.do?ui=2025480316
  - 出处：https://www.cnki.com.cn/Article/CJFDTotal-SPYK200702002.htm#1
- **c2** 马齿苋泡水能防止心血管动脉硬化，对癌症病人有帮助
  - 原话：「还有很好的防止心血管的动物硬化」
  - 标签：**部分正确**（partial）— 来源支持马齿苋调血脂抗动脉硬化，但无癌症病人获益证据
  - 出处：https://www.xtshos.com.cn/Html/News/Articles/6792.html
  - 出处：http://mlszyyy.com/mile/kepuwenhua/1725.html
  - 出处：https://d.wanfangdata.com.cn/periodical/CihQZXJpb2RpY2FsQ0hJU29scjkyMDI2MDYxMDIwMjYwNjEwMTYxMjM4Eg96Z2dnd3MyMDA0MDEwMTkaCHR4Z3drcXNp
- **c3** 大蒜含硒元素和大蒜素，能提高免疫力、抑制幽门螺杆菌，降低患胃癌风险
  - 原话：「可以降低患癌的风险」
  - 标签：**部分正确**（partial）— 来源支持大蒜成分及降低胃癌风险，但抑制幽门螺杆菌和提高免疫力表述不充分
  - 出处：https://mpapi.bjcancer.org/Html/News/Articles/10587.html
  - 出处：https://literature.chinacdc.cn/xuekefuwu/gonggongweishengxueshuredianzhuiz/201909/t20190926_205825.html
  - 出处：https://www.sciencedirect.com/science/article/pii/S0002916522105307#1
- **c4** 绿茶中的茶多酚能阻断亚硝胺合成，预防癌症和高血脂
  - 原话：「能够阻断亚硝胲在人体内的合成」
  - 标签：**部分正确**（partial）— 来源支持茶多酚抑制亚硝化，但预防癌症和高血脂证据不足或为动物实验
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S1383571897001782#1
  - 出处：https://www.sciencedirect.com/topics/medicine-and-dentistry/black-tea-extract#2
  - 出处：https://www.jstage.jst.go.jp/article/jems/26/3/26_3_265/_article#1

## ⬜ 待确认 · keto-cancer · 癌症克星——生酮饮食

https://www.bilibili.com/video/BV1K6CdB1EzS（0 播放）

- **c1** 生酮饮食指不吃糖和面包、意大利面等会转化为糖的淀粉类碳水化合物
  - 原话：「no sugar and no starchy carbohydrates」
  - 标签：**部分正确**（partial）— 来源确认为极低碳水饮食，但未提“转化为糖的淀粉”这一表述，且严格程度被简化
  - 出处：https://jiankang.cctv.com/2025/08/14/ARTIju5ptKjPM5FvueizEBr2250814.shtml#1
  - 出处：https://cdcp.gd.gov.cn/jkjy/jkzt/yyyspaq/content/post_4709390.html#1
- **c2** 癌细胞依赖糖和淀粉中的葡萄糖生存
  - 原话：「cancer cells love sugar and starch」
  - 标签：**部分正确**（partial）— 来源称癌细胞大量消耗葡萄糖，但未说只依赖糖和淀粉
  - 出处：http://staging.europepmc.org/backend/articlerender.fcgi?accid=PMC4615071#1
  - 出处：https://pubmed.ncbi.nlm.nih.gov/?term=35620573+34033261+33892108+31996711+31340585+31306426+30270319+29981891+29529525+29462809+29459024+29339110+28859155+28359800+27791278+27410235+27261584+27223849+26854130+26160659+25907369+25796090+25502934+25240061+25091860+24204635+23541363+22819688+22796500+22717091+22476082+21978418+21777645+21555120+21511450+21510766+20927436+18948178+18487028+18355922+17868184+16182371+11991231+10783904&format=abstract&size=200#4
- **c3** 去除葡萄糖可以饿死癌细胞
  - 原话：「remove the glucose and starve the cancer cells」
  - 标签：**错误**（wrong）— 权威来源指出媒体将基础研究误读为饿死癌细胞，该说法不客观
  - 出处：http://paper.people.com.cn/rmrbhwb/html/2014-06/28/content_1446781.htm#1
  - 出处：http://6d.dxy.cn/article/78895
- **c4** 正常细胞能改用酮体供能，癌细胞缺乏这种代谢灵活性
  - 原话：「cancer cells lack this metabolic flexibility」
  - 标签：**错误**（wrong）— Nature来源明确癌细胞能高效利用酮体，与说法矛盾
  - 出处：https://www.nature.com/articles/cr2016110#1

## ⬜ 待确认 · thick-blood · 血脂高、血液太浓，倪师教你一招

https://www.bilibili.com/video/BV1AC4y1f7z3（0 播放）

- **c1** 口渴与否可以判断血液浓度是否正常
  - 原话：「口渴不渴就知道」
  - 标签：**部分正确**（partial）— 来源称口渴时已明显缺水，不能仅凭口渴判断血液浓度正常
  - 出处：https://www.sqszxxz.cn/?200.html
  - 出处：https://www.bhblood.com/index.php/site/page/index/2535/news_id/193756/category_id/134419/ct_id/297/okcode/af8f12e191699242efd619e6614d18ad00d208d4e58198b33c625c7c2f76073a
  - 出处：https://www.cnma.org.cn/nd.jsp?id=4433&groupId=-1
- **c2** 吃蔗糖或喝甘蔗汁能稀释血液、降低血浓度
  - 原话：「甘蔗汁就把血稀释掉」
  - 标签：**错误**（wrong）— 权威来源明确否定甘蔗汁活血化瘀说法
  - 出处：https://www.vietnam.vn/zh-cn/su-that-ve-ly-nuoc-mia-sa-gung-goi-mau-ve
- **c3** 所有酸味的东西都会影响脾胃
  - 原话：「所有酸味的东西全部会影响到脾胃」
  - 标签：**部分正确**（partial）— 来源称适度食酸可健运脾胃，过量才碍胃伤脾，非所有酸味都影响
  - 出处：https://wsjk.tj.gov.cn/JKJY5233/JKZS7782/202008/t20200828_3579793.html
  - 出处：https://health.cnr.cn/jkgdxw/20230926/t20230926_526433020.shtml#1
- **c4** 血糖高的人也可以吃正常的糖
  - 原话：「这不吃正常的糖」
  - 标签：**部分正确**（partial）— 来源称糖尿病无绝对禁食但需限量，避免精制糖；说法夸大
  - 出处：https://health.ntuh.gov.tw/health/new/6289.html
  - 出处：https://wsjkw.henan.gov.cn/2011/09-09/1276641.html

## ⬜ 待确认 · gout-water · 倪海厦：尿酸高痛风，一杯水就能解决，还能净化肾脏

https://www.bilibili.com/video/BV17D4217713（0 播放）

- **c1** 不需要购买酸碱水机器，这类机器都是骗人的
  - 原话：「不用花钱去买机器」
  - 标签：**部分正确**（partial）— 权威来源指碱性水治病宣传是骗局，但未断言所有机器都骗人
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=7304870260708962304#1#1#1
- **c2** 柠檬味道虽酸但属于纯碱
  - 原话：「柠檬是纯碱」
  - 标签：**部分正确**（partial）— 来源称柠檬为碱性食物，但非“纯碱”，且原汁呈酸性
  - 出处：https://cloud.kepuchina.cn/h5/detail?id=6969020931225604096
  - 出处：https://kmweb.moa.gov.tw/knowledge_view.php?id=9852
- **c3** 喝柠檬水能治好痛风
  - 原话：「你吃柠檬水就好了」
  - 标签：**错误**（wrong）— 来源明确柠檬水仅辅助降尿酸，不能治疗痛风
  - 出处：https://m.dayi.org.cn/qa/275862.html
  - 出处：https://jbk.39.net/tf/230916/u7ff41q.html
- **c4** 柠檬水应在午餐后喝，晚上不要喝
  - 原话：「中餐以后吃」
  - 标签：**部分正确**（partial）— 有来源支持午饭后喝，但无权威来源明确禁止晚上喝，说法绝对化
  - 出处：https://wsjkw.gxzf.gov.cn/xxgk_49493/fdzdgk/ggws/jkkp/jkzs/t5699806.shtml
  - 出处：https://h5.baike.qq.com/mobile/article.html?docid=qa12824011z5axqv&VNK=8ba69f03

## ⬜ 待确认 · white-hair-trick · 白发变黑一招搞定—倪师详解

https://www.bilibili.com/video/BV1Bw411U7nc（0 播放）

- **c1** 每天喝半勺经验方，一个月头发就能变黑
  - 原话：「每天就喝个半勺 1个月头发就变黑了」
  - 标签：**部分正确**（partial）— 来源称效果因人而异，未保证一个月变黑
  - 出处：https://m.dayi.org.cn/qa/326062.html#1
- **c2** 生地是滋补的药，可以吃
  - 原话：「生地是滋补的药」
  - 标签：**部分正确**（partial）— 生地能滋阴生津，但性寒清热，非泛指滋补，脾胃虚寒者慎用
  - 出处：https://spbcm2.cmu.edu.tw/ccmp/c/c1723.htm
  - 出处：https://m.dayi.org.cn/qa/368410.html#1
  - 出处：http://paper.dzjkb.org.cn/article/33577/20002.html
- **c3** 茜草没有毒，可以吃
  - 原话：「茜草又没有毒 当然没有关系 你可以吃」
  - 标签：**部分正确**（partial）— 来源称无毒但需限量、有禁忌，不能随意吃
  - 出处：http://s.dayi.org.cn/mip/s/qa/334442_t.html
  - 出处：http://s.dayi.org.cn/mip/s/cmedical/1115082.html#introduction#1#1
- **c4** 中医认为发为血余，头发是血多余部分所化
  - 原话：「发为血余」
  - 标签：**部分正确**（partial）— 来源称发为血之余、头发为血延续，但未说“多余部分所化”，表述有夸大
  - 出处：http://health.people.com.cn/n/2015/0911/c21471-27573397.html
  - 出处：https://cloud.kepuchina.cn/newSearch/imgText?id=6969173222872240128#1

## ⬜ 待确认 · fruit-plaque · 3种水果，是血管清洁工，冲走血栓斑块，血管柔软

https://www.bilibili.com/video/BV1RNC2YMEUq（0 播放）

- **c1** 苹果含有的果胶质（可溶性纤维）有助于降低低密度胆固醇
  - 原话：「助于低密度胆固醇的降低」
  - 标签：**正确**（correct）— 权威来源称苹果果胶能降低坏胆固醇
  - 出处：https://www.fuwai.com/News/Articles/Index/207007
  - 出处：https://www.sciencedirect.com/science/article/abs/pii/S0022316623073832?via%3Dihub
- **c2** 经常吃苹果的人胆固醇含量比不常吃苹果的人低20%
  - 原话：「胆固醇含量比不经常吃苹果的人低20」
  - 标签：**无法核实**（unverifiable）— 来源仅称苹果有助降胆固醇，未支持20%具体数值
  - 出处：https://m.dayi.org.cn/qa/149257#1
  - 出处：https://m.dayi.org.cn/qa/226548#1
  - 出处：http://sklcvd.fuwaihospital.org/News/Articles/Index/207012
- **c3** 葡萄含有的白藜芦醇是降低胆固醇的天然物质
  - 原话：「含有白黎芦醇，是降低胆固醇的天然物质」
  - 标签：**部分正确**（partial）— 来源称白藜芦醇抗氧化、影响脂质代谢，但未证实直接降低胆固醇
  - 出处：https://cancer.commonhealth.com.tw/article/731?rec=ch-cancer-i2i-1-visitor&from_website=ch_cancer&from_id=article-589&from_order=7&from_area=area03&from_index=7
  - 出处：https://www.commonhealth.com.tw/article/89094
  - 出处：https://www.eurekaselect.com/article/135128/cn#1
- **c4** 补充纳质素（纳豆激酶类）可降低血液粘稠度、抗凝血、加速血栓溶解
  - 原话：「纳至素具有降低血液粘稠度、抗凝血的作用」
  - 标签：**部分正确**（partial）— 动物实验和单次口服研究支持溶栓抗凝，但人体证据不足，说法夸大
  - 出处：https://www.sinomed.ac.cn/article.do?ui=2021432732
  - 出处：https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-24650412/
  - 出处：https://iptt.sinica.edu.tw/shares/667

## ⬜ 待确认 · glucose-points · 身上有4个天然的“降糖穴，每天按摩3分钟，血糖或许逐渐降下来

https://www.bilibili.com/video/BV1mq4y157Ko（0 播放）

- **c1** 按揉然谷穴相当于人体自带的二甲双胍，能帮助降糖
  - 原话：「就相当于是人体自带的二甲双胍」
  - 标签：**部分正确**（partial）— 来源称然谷穴有助降糖，但未称等同二甲双胍，属夸大
  - 出处：https://health.cnr.cn/jkgdxw/20161110/t20161110_523255935.shtml
  - 出处：http://szyyj.gd.gov.cn/zyyfw/ysbj/content/post_4358810.html
  - 出处：http://health.people.com.cn/n1/2016/0912/c21471-28708077.html
- **c2** 按揉大鱼际可滋阴清热润肺生津止渴，从而达到降糖作用
  - 原话：「从而达到降糖的一个作用」
  - 标签：**部分正确**（partial）— 来源支持清热润肺生津止渴，但降糖仅为辅助调理，须遵医嘱
  - 出处：http://szyyj.gd.gov.cn/zyyfw/ysbj/content/post_4358810.html
  - 出处：https://www.lunan.com.cn/Home/News/newsDetail/id/11039/nid/41.html
- **c3** 按揉内庭穴可清胃泻火养阴增液，改善糖尿病中消症状
  - 原话：「改善糖尿病中消的症状」
  - 标签：**正确**（correct）— 广东省中医药局等来源明确内庭穴清胃泻火、养阴增液，改善中消
  - 出处：http://szyyj.gd.gov.cn/zyyfw/ysbj/content/post_4358810.html
  - 出处：https://jk.zdjt.com/a/41055/t/yf/i/
  - 出处：https://health.ltn.com.tw/article/breakingnews/4555289#1
- **c4** 按揉关元穴可滋阴固肾、培元固本，改善糖尿病患者多尿症状
  - 原话：「改善糖尿病患者下消的症状」
  - 标签：**部分正确**（partial）— 仅权威度3的科普文提及按揉关元滋阴固肾改善多尿，权威研究为针刺/温针灸非按揉
  - 出处：https://jk.zdjt.com/a/41055/t/yf/i/
  - 出处：https://d.wanfangdata.com.cn/periodical/zjlczz202003010

## ⬜ 待确认 · liver-detox · 8种排毒和清洁肝脏的最佳食谱

https://www.bilibili.com/video/BV1hfcUeDEsf（0 播放）

- **c1** 菠菜有助于稳定血糖从而减少食欲
  - 原话：「菠菜的一个好处是它能减少食欲」
  - 标签：**部分正确**（partial）— 有来源支持菠菜抑制食欲，但稳定血糖证据不足，且动物实验为主
  - 出处：https://pubmed.ncbi.nlm.nih.gov/28238891/#1
  - 出处：https://health.ltn.com.tw/article/breakingnews/3332840
  - 出处：https://health.businessweekly.com.tw/article/ARTL000032093
- **c2** 葡萄柚能促进肝脏胆汁分泌帮助分解脂肪
  - 原话：「它能帮助促进肝脏的胆汁分泌」
  - 标签：**部分正确**（partial）— 来源称葡萄柚/精油刺激胆汁分泌助消化脂肪，但未明确促进肝脏分泌，且部分为精油或科普站
  - 出处：http://s.dayi.org.cn/mip/s/qa/329754_t.html
  - 出处：https://www.chemicalbook.cn/ProductChemicalPropertiesCB3707492.htm#1
  - 出处：https://baike.baidu.com/item/%e8%91%a1%e8%90%84%e6%9f%9a%e5%8f%a3%e6%9c%8d%e7%b2%be%e6%b2%b9/11030054
  - 出处：http://news.ymt.com/health_product/xAGVQAd0
- **c3** 羽衣甘蓝能帮助肝脏排毒和抗炎
  - 原话：「具有帮助肝脏排毒的额外特性」
  - 标签：**正确**（correct）— 多个权威来源均称羽衣甘蓝支持肝脏解毒酶、抗氧化抗炎
  - 出处：https://health.tvbs.com.tw/nutrition/366449?from=extend
  - 出处：https://jbk.39.net/gy/240426/o1otjov.html
  - 出处：https://jbk.39.net/fx/240112/w5lpvkf.html
  - 出处：https://jbk.39.net/fx/240222/j1mvhy7.html
  - 出处：https://continentalhospitals.com/zh-CN/blog/foods-that-promote-liver-health#1
- **c4** 黄瓜有助于预防非酒精性脂肪肝病
  - 原话：「黄瓜有助于预防非酒精性脂肪肝病」
  - 标签：**部分正确**（partial）— 来源称黄瓜低热量助减重、作为清淡饮食一部分有益，但明确不能治疗脂肪肝，说法夸大
  - 出处：https://jbk.39.net/zfg/240830/l5s9fwf.html
  - 出处：https://jbk.39.net/zfg/240924/t3t7p0q.html
  - 出处：https://jbk.39.net/zfg/240922/t7t3wdw.html

## ⬜ 待确认 · lipid-points · 按揉这两个穴位可以降血脂

https://www.bilibili.com/video/BV1Mb4y1H7ks（0 播放）

- **c1** 揉按后溪穴能够降血脂
  - 原话：「这个地方能够降血脂」
  - 标签：**无法核实**（unverifiable）— 来源仅述后溪穴调颈椎等功效，未提及降血脂
  - 出处：http://yc3yy.com/jkzsShow3433.html
  - 出处：http://shlhzj.com/archiver/?tid-4846.html
- **c2** 按压丰隆穴能起到降脂减肥的作用
  - 原话：「能够起到一个降脂减肥的作用」
  - 标签：**部分正确**（partial）— 来源称丰隆穴可祛湿化痰、助减重降脂，但未直接证实按压即降脂减肥
  - 出处：https://health.udn.com/health/tagging/%e8%b6%b3%e4%b8%89%e9%87%8c
  - 出处：https://m.dayi.org.cn/qa/156020
  - 出处：http://szyyj.gd.gov.cn/zyyfw/ysbj/content/post_4019767.html
- **c3** 每天按两三次、每次几分钟并坚持，血脂会慢慢降下来
  - 原话：「每天按个两三次」
  - 标签：**部分正确**（partial）— 来源称穴位按摩为辅助手段，不能替代药物，未证实具体频次可降血脂
  - 出处：https://jbk.39.net/gxz/230921/a6fs4qi.html
  - 出处：http://www.gzswssy.com/paper/2026-2/6/30983.shtml

## ⬜ 待确认 · berg-breathing · 60 秒快速降血压的呼吸法！高血压原因，自然疗法，伯格医生 Dr Berg

https://www.bilibili.com/video/BV1X7421P7NH（0 播放）

- **c1** 低盐饮食实际上可能使血压升高
  - 原话：「低盐饮食实际上使高血压升高」
  - 标签：**部分正确**（partial）— 有来源支持长期低盐可升压，但其他权威来源显示低盐降压，说法以偏概全
  - 出处：https://www.tandfonline.com/doi/10.1080/10641963.2018.1545850#1
  - 出处：https://europepmc.org/article/PMC/3817896#1
- **c2** 增加钾摄入比减少钠摄入对控制高血压更重要
  - 原话：「增加钾比少吃盐更重要」
  - 标签：**部分正确**（partial）— 来源支持补钾重要，但未证明其比限钠更重要
  - 出处：https://m.medlive.cn/cms/research/207752#1
  - 出处：https://cmtopdr.com/post/detail/e1c6cca8-101f-4b03-9a8f-5dbfe62208b6#1
- **c3** 每天需要摄入4700毫克钾
  - 原话：「每天需4700毫克的钾」
  - 标签：**部分正确**（partial）— 来源给出分年龄性别AI值，4700mg非普适每日需求
  - 出处：https://brighamandwomens.staywellsolutionsonline.com/YourFamily/Women/19,Potassium#1
  - 出处：https://ods.od.nih.gov/pdf/factsheets/Potassium-DatosEnEspanol.pdf#1#1
- **c4** 补充维生素D可能解决高血压问题
  - 原话：「只要多吃D就可解决」
  - 标签：**部分正确**（partial）— 来源显示维生素D与高血压相关，但未证实补充可解决高血压
  - 出处：https://www.ahajournals.org/doi/10.1161/CIRCULATIONAHA.107.713339#2
  - 出处：https://journals.lww.com/jasn/fulltext/10.1681/asn.20233411s1637a~paradoxical-association-of-vitamin-d-supplementation-with#1
