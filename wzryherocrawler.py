import csv
import json
import os
import time

import lxml.html
import matplotlib
import requests
from matplotlib import pyplot as plt
from selenium import webdriver

headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:68.0) Gecko/20100101 Firefox/68.0"}

# #######外部调节参数#######
# 调试模式
debug_mode = False
# 用Firefox或者Chrome自动爬取
run_with_firefox = True
# 写入文本文件编码格式
write_text_code_type = 'utf-8'
# 存储根目录
dir_name = './wz_hero'


def makedir(dir_str):
    """
    文件夹不存在时创建文件夹
    :param dir_str: 路径
    """
    if not os.path.exists(dir_str):
        os.makedirs(dir_str)
        print('Create dir:%s' % dir_str)


base_url = 'https://pvp.qq.com/web201605/'
main_url = base_url + 'herolist.shtml'

# Web driver对象
driver_cache = None
# 分目录（不要修改，修改这里没用）
pic_dir = wallpaper_dir = ''
# JSON文件名
json_file_name = 'dump_skins.json'
# CSV文件名
csv_file_name = 'hero_list.csv'


def make_web_driver():
    """制造web driver"""
    # 原理：web driver定义耗时较多，缓存web driver（在同一个session下）可以提高速度，但是内存占用会缓慢提升
    global driver_cache
    if driver_cache is None:
        print('Load web driver')
        if run_with_firefox:
            # selenium Firefox
            options = webdriver.FirefoxOptions()
            profile = webdriver.FirefoxProfile()
            # True=无UI，加快加载速度
            # 调试需要查看浏览器
            options.headless = not debug_mode
            profile.set_preference('permissions.default.image', 2)  # 禁止加载图片
            profile.set_preference('permissions.default.stylesheet', 2)  # 禁止css
            driver_cache = webdriver.Firefox(options=options, firefox_profile=profile)
        else:
            # selenium Chrome
            options = webdriver.ChromeOptions()
            if not debug_mode:
                options.add_argument('--headless')
            options.add_argument('--disable-extensions')  # 禁用扩展
            options.add_argument('blink-settings=imagesEnabled=false')
            options.add_argument('user-agent=' + headers['User-Agent'])  # 修改UA
            driver_cache = webdriver.Chrome(options=options)
    else:
        if debug_mode is True:
            # 这里可看到session
            print(driver_cache)
    return driver_cache


def wz_fetch_main_website():
    """
    拉取主网页内容
    :return: main_html_body
    """
    print("拉取英雄资料页面内容")
    print("Fetch main")
    url_code_type = 'gbk'  # web编码类型
    main_response = requests.get(main_url, headers=headers)
    main_html_body = main_response.content.decode(url_code_type)
    main_response.close()
    return main_html_body


def wz_parse_all_hero_content(main_html_body):
    """
    从主网页解析英雄内容
    :param main_html_body: 主网页内容
    :return: all_hero_content
    """
    print("解析所有英雄内容")
    etree = lxml.html.etree
    main_parser = etree.HTML(main_html_body)
    all_hero_content = main_parser.xpath("//div[@class='herolist-content']/ul/li/a/*")

    # 调试用，下载一部分
    max_download_count = 5
    if debug_mode:
        all_hero_content = all_hero_content[:max_download_count]
    return all_hero_content


def wz_parse_all_hero_data(all_hero_content):
    """
    解析英雄数据
    :param all_hero_content: (多个)英雄内容
    :return:all_hero_data
    """
    print("解析所有英雄数据")
    all_hero_data = []
    # 拉取英雄列表
    for hero_data in all_hero_content:
        hero = {}
        print("Hero data loop:", len(all_hero_data))

        # 名字
        name = hero_data.xpath("../text()")[0]
        hero['name'] = name

        # 图片 Logo 链接
        pic = "https:" + hero_data.xpath("../img/@src")[0]
        hero['pic'] = pic

        # 英雄链接
        link = base_url + hero_data.xpath("../@href")[0]
        hero['link'] = link

        # 拉取英雄详情
        print('Fetch Hero:' + name)
        # hero_response = requests.get(link, headers=headers)
        # hero_web_body = hero_response.content.decode(url_code_type)
        # 由于这部分使用JS动态加载，因此用selenium调用浏览器获取加载后的网页
        driver = make_web_driver()
        driver.get(link)
        hero_web_body = driver.page_source
        hero_parser = lxml.html.etree.HTML(hero_web_body)

        '''
        # 一开始就显示的图片 big skin 链接
        wallpaper_raw = hero_parser.xpath("//div[@class='zk-con1 zk-con']/@style")[0]
        wallpaper = 'https:' + wallpaper_raw[wallpaper_raw.index('\'') + 1:wallpaper_raw.rindex('\'')]
        hero.append(wallpaper)
        '''

        # 图片 big skin 链接
        base_skin_xpath = "//ul[@class='pic-pf-list pic-pf-list3']/"
        wallpapers = hero_parser.xpath(base_skin_xpath + "li/i")
        wallpaper_list = []
        for wallpaper in wallpapers:
            wallpaper_url = 'https:' + wallpaper.xpath("./img/@data-imgname")[0]
            wallpaper_list.append(wallpaper_url)
        hero['wallpaper_list'] = ' '.join(wallpaper_list)

        # 皮肤名列表
        skin_name_list = hero_parser.xpath(base_skin_xpath + "@data-imgname")[0]
        print('Skin info:', (name, skin_name_list))
        hero['skin_name_list'] = skin_name_list

        # 属性 data-bar 1到4
        attrs = []
        for i in range(1, 5):
            attr = hero_parser.xpath("//span[@class='cover-list-bar data-bar" + str(i) + " fl']/i/@style")[0][6:9]
            if '%' not in attr:
                attr += '%'
            attrs.append(attr)
        hero['attrs'] = attrs

        # 打包
        all_hero_data.append(hero)

        # 结束显示和退出驱动
        if len(all_hero_data) == len(all_hero_content):
            print('Read links finished')
            driver.quit()
            del driver
    return all_hero_data


def wz_make_dir():
    """创建目录"""
    # 目录路径
    print("目录初始化")
    global pic_dir, wallpaper_dir
    pic_dir = dir_name + '/picture'  # Logo目录
    wallpaper_dir = dir_name + '/wallpaper'  # Big skin目录

    # 创建目录
    makedir(dir_name)
    makedir(pic_dir)
    makedir(wallpaper_dir)


def wz_prepare_csv_file():
    """
    准备CSV文件......
    创建CSV文件对象，写入表头，并返回CSV文件对象以写入数据
    :return: csv_file
    """
    print("准备英雄数据CSV文件")
    print('Prepare CSV')
    csv_path = dir_name + '/' + csv_file_name
    csv_file = open(csv_path, "w", encoding=write_text_code_type)
    # BUG FIX:is -> ==
    if write_text_code_type == 'utf-8':
        # 兼容Excel (utf-8 with BOM)
        csv_file.write('\uFEFF')
    csv_file.write(','.join(
        ['Name', 'Logo Link', 'Link', 'Wallpaper Links', 'Skin Name List',
         '生存能力', '攻击伤害', '技能效果', '上手难度']) + '\n')
    return csv_file


def wz_write_csv_data(all_hero_data, csv_file):
    """
    写入CSV文件数据
    :param all_hero_data: (多个)英雄数据
    :param csv_file: CSV文件对象
    """
    print("写入英雄CSV文件数据")
    print('Write CSV data')
    # csv 文件数据写入
    for hero_element in all_hero_data:
        # csv 文件数据写入
        hero_attrs_str = ','.join(hero_element['attrs'])
        csv_file.write(','.join([hero_element['name'],
                                 hero_element['pic'],
                                 hero_element['link'],
                                 hero_element['wallpaper_list'],
                                 hero_element['skin_name_list'],
                                 hero_attrs_str]) + '\n')
    csv_file.close()


def wz_write_skin_data_json(all_hero_data):
    """
    写入皮肤数据JSON
    :param all_hero_data: (多个)英雄数据
    """
    # 皮肤JSON写入
    print("写入皮肤壁纸CSV文件")
    print('Write skins json')
    json_data = []
    for i in range(len(all_hero_data)):
        # 单个英雄
        simple_hero_skin_data = {'hero': all_hero_data[i]['name']}
        j = 0
        simple_hero_skin_list = []
        for skin_name in all_hero_data[i]['skin_name_list'].split('|'):
            # 单个皮肤
            minimal_hero_skin_data = {'name': skin_name, 'link': all_hero_data[i]['wallpaper_list'].split(' ')[j]}
            simple_hero_skin_list.append(minimal_hero_skin_data)
            j += 1
        simple_hero_skin_data['skins'] = simple_hero_skin_list
        json_data.append(simple_hero_skin_data)
    json_file = open(dir_name + '/' + json_file_name, 'w', encoding=write_text_code_type)
    json_file.write(json.dumps(json_data, ensure_ascii=False, indent='\t'))
    json_file.close()


def wz_write_image_file(all_hero_data):
    """
    写入图像文件
    :param all_hero_data: (多个)英雄数据
    """
    print("写入图像文件")
    print('Write image files')
    i = 0
    for hero_element in all_hero_data:

        # 图像文件写入
        # Logo
        pic_file = open(pic_dir + '/' + hero_element['name'] + '.jpg', 'wb')
        pic_response = requests.get(hero_element['pic'])
        pic_file.write(pic_response.content)
        pic_response.close()  # 关闭连接防止被断开连接
        # Big skin
        j = 0
        for wallpaper_element in hero_element['wallpaper_list'].split(' '):
            hero_wallpaper_dir = wallpaper_dir + '/' + hero_element['name']
            makedir(hero_wallpaper_dir)
            name = hero_element['name']
            skin_name = hero_element['skin_name_list'].split('|')[j]
            print('Write big skin:%d %s %d %s' % (i, name, j, skin_name))
            wallpaper_file = open(hero_wallpaper_dir + '/' + '{}-{}'.format(name, skin_name) + '.jpg', 'wb')
            wallpaper_response = requests.get(wallpaper_element)
            wallpaper_file.write(wallpaper_response.content)
            wallpaper_response.close()
            wallpaper_file.close()
            j += 1

        # 关闭文件释放资源
        pic_file.close()
        i += 1


def wz_draw_hero_skin_count_stat_data():
    """分析JSON输出英雄皮肤个数统计柱形图"""
    print("输出英雄皮肤个数统计柱形图")
    stat_pic_file_name = 'hero_skin_count_stat.png'
    file = open(dir_name + '/' + json_file_name, 'r', encoding=write_text_code_type)
    data = json.loads(file.read())
    name_list = []
    count_list = []
    for hero_element in data:
        name_list.append(hero_element['hero'])
        count_list.append(len(hero_element['skins']))
    x = [i for i in range(len(name_list))]
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.figure(figsize=(26, 15), dpi=100)  # 画布大小
    plt.grid(alpha=0.1)
    plt.title('英雄皮肤个数统计柱形图')
    plt.bar(x, count_list, width=0.8, color='b')  # 条形图
    plt.xlabel('英雄名称')
    plt.ylabel('皮肤个数')
    plt.xticks(x, name_list, rotation=75)  # 调整 x 刻度
    plt.xlim(-1, len(name_list) + 1)  # 设置 x 轴的最小最大值
    plt.savefig(dir_name + '/' + stat_pic_file_name)
    if debug_mode:
        plt.show()


def wz_draw_hero_attr_stat_data():
    """分析CSV输出英雄属性统计散点图"""
    print("输出英雄属性统计散点图")
    stat_pic_file_name = 'hero_attr_count_stat.png'
    reader = csv.reader(open(dir_name + '/' + csv_file_name, 'r', encoding=write_text_code_type))
    name_list = []
    skill1_list = []
    skill2_list = []
    skill3_list = []
    skill4_list = []
    list_without_header = [e for e in reader][1:]
    for element in list_without_header:
        name_list.append(element[0])
        skill1_list.append(int(element[5][:-1]))
        skill2_list.append(int(element[6][:-1]))
        skill3_list.append(int(element[7][:-1]))
        skill4_list.append(int(element[8][:-1]))
    font = {'family': 'SimHei'}
    matplotlib.rc('font', **font)
    plt.figure(figsize=(36, 18), dpi=120)
    plt.suptitle('英雄属性统计散点图')
    x = range(len(name_list))
    y = range(0, 101, 10)
    skill_name_list = ['生存能力', '攻击伤害', '技能效果', '上手难度']
    color_list = ['#1c8fea', '#e7ca63', '#5dd473', '#e84a33']  # 颜色获取自官网进度条颜色
    all_skill_data_list = [skill1_list, skill2_list, skill3_list, skill4_list]
    # 分割成四个小图
    for i in range(4):
        plt.subplot(2, 2, i + 1)
        plt.title(skill_name_list[i])
        plt.grid(linestyle='-.', alpha=0.3)
        plt.xlabel('英雄名称')
        plt.ylabel('强度(单位:%)')
        plt.xticks(x, name_list, rotation=90)
        plt.yticks(y)
        plt.plot(x, all_skill_data_list[i], 'o', color=color_list[i])
        plt.xlim(-1, len(name_list) + 1)
    plt.savefig(dir_name + '/' + stat_pic_file_name)
    if debug_mode:
        plt.show()
    pass


if __name__ == '__main__':
    # 开始计时
    start_time = time.time()

    # 事务处理
    main_website_content = wz_fetch_main_website()
    all_hero_content_data = wz_parse_all_hero_content(main_website_content)
    all_hero_object_data = wz_parse_all_hero_data(all_hero_content_data)
    wz_make_dir()
    all_hero_csv_file = wz_prepare_csv_file()
    wz_write_csv_data(all_hero_object_data, all_hero_csv_file)
    wz_write_skin_data_json(all_hero_object_data)
    wz_write_image_file(all_hero_object_data)
    wz_draw_hero_skin_count_stat_data()
    wz_draw_hero_attr_stat_data()

    # 成功结束，输出脚本执行时间
    print('Successfully ended:In', round(time.time() - start_time), 'seconds.')
