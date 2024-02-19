import os
import re
import inquirer
import requests
from bs4 import BeautifulSoup
import pandas as pd
from model import UserInfo, user_infos_from_dict


def save_all_users(users, save_path, format='excel'):
    df = pd.DataFrame(users, columns=[
                      'id', 'name', 'created_at', 'sortable_name', 'short_name', 'email'])
    if format == 'excel':
        df.to_excel(save_path, index=False)
    elif format == 'csv':
        df.to_csv(save_path, index=False)


if __name__ == '__main__':
    session = requests.session()
    login_url = 'https://oc.sjtu.edu.cn/login/openid_connect'
    courses_url = 'https://oc.sjtu.edu.cn/courses'
    while True:
        if os.path.exists('JAAuthCookie.txt'):
            print('检测到已保存的 JAAuthCookie，加载...', end='')
            with open('JAAuthCookie.txt', 'r') as f:
                JAAuthCookie = f.read()
            print('Done.')
        else:
            JAAuthCookie = input(
                "请从 https://jaccount.sjtu.edu.cn/jaccount/ 的 Cookies 中正确复制 'JAAuthCookie' 字段：\n")
        login_cookies = {
            'JAAuthCookie': JAAuthCookie,
        }
        print('现在开始登录...')
        res = session.get(login_url, cookies=login_cookies)
        if res.status_code == 200 and not "https://jaccount.sjtu.edu.cn/jaccount/jalogin" in res.request.url:
            print('登录成功！保存最新的 JAAuthCookie...', end='')
            with open('JAAuthCookie.txt', 'w') as f:
                f.write(JAAuthCookie)
            print('Done')
            break
        elif os.path.exists('JAAuthCookie.txt'):
            print('登录失败！删除旧的 JAAuthCookie...', end='')
            os.remove('JAAuthCookie.txt')
            print('Done')
        else:
            print("登录失败！")

    print('开始搜索可用的课程...', end='')
    content = session.get(courses_url).content
    soup = BeautifulSoup(content, 'html.parser')
    trs = soup.find_all(
        'tr', {'class': 'course-list-table-row'})

    target_courses = []
    target_enrolled_as = []
    for tr in trs:
        course = tr.find(
            'a', {'title': True, 'href': re.compile(r"/courses/\d+")})
        if course is None:
            continue
        enrolled_as = tr.find(
            'td', {'class': 'course-list-enrolled-as-column'})
        target_courses.append((course.get('title'), re.findall(
            r"/courses/(\d+)", course.get('href'))[0]))
        target_enrolled_as.append(enrolled_as.get_text().strip())
    courses = [(t[0], t[1], s)
               for t, s in zip(target_courses, target_enrolled_as)]
    print('Done')

    courses = list(filter(lambda x: x[2] == '助教', courses))
    if len(courses) == 0:
        print('没有可用的课程！')
        exit(0)

    courses_selection = [
        course[0]
        for course in courses
    ]
    questions = [
        inquirer.List('course',
                      message="请选择课程",
                      choices=courses_selection
                      )]

    selected_course_name = inquirer.prompt(questions)['course']
    print(f'你选择了课程 "{selected_course_name}"')
    selected_course = list(
        filter(lambda x: x[0] == selected_course_name, courses))[0]

    course_id = selected_course[1]
    per_page = 50
    print('正在读取名单...')
    page_index = 1
    all_users = []

    while True:
        try:
            print(f"读取第{page_index}页数据.")
            url = f'https://oc.sjtu.edu.cn/api/v1/courses/{course_id}/users?per_page={per_page}&page={page_index}'
            res = session.get(url)
            data = res.json()
            users = user_infos_from_dict(data)
            if len(users) == 0:
                break
            all_users.extend(users)
            page_index += 1
        except Exception as e:
            print(e)
            break

    all_users = [(user.id, user.name, user.created_at, user.sortable_name, user.short_name, user.email)
                 for user in all_users]

    questions = [inquirer.Confirm('need_save', message="是否需要保存名单")]
    need_save = inquirer.prompt(questions)['need_save']

    if need_save:
        questions = [
            inquirer.List('format', message="请输入保存格式：",
                          choices=['csv', 'excel']),
            inquirer.Text('save_path', message="请输入保存路径")]
        answers = inquirer.prompt(questions)
        format = answers['format']
        save_path = answers['save_path']
        save_all_users(all_users, save_path, format)
        print('保存成功！')
