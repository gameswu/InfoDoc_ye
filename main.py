import os
import yaml
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("infodoc_ye", "gameswu", "Info与EULA管理插件", "1.0.0")
class InfoDocPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_dir = os.path.dirname(__file__)
        # 二级父目录路径
        self.data_dir = os.path.dirname(os.path.dirname(self.plugin_dir))
        self.info_links_file = os.path.join(self.plugin_dir, "info_links.yaml")
        self.user_eula_file = os.path.join(self.data_dir, "user_eula_status.yaml")
        self.info_links = {}
        self.user_eula_status = {}

    async def initialize(self):
        """插件初始化方法"""
        await self.ensure_data_files_exist()
        await self.load_config_files()
        logger.info("InfoDoc插件已初始化")

    async def ensure_data_files_exist(self):
        """确保数据文件存在，如果不存在则创建"""
        try:
            # 确保二级父目录存在
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info(f"数据目录路径: {self.data_dir}")
            
            # 检查并创建用户EULA状态文件
            if not os.path.exists(self.user_eula_file):
                default_eula_data = {'users': {}}
                with open(self.user_eula_file, 'w', encoding='utf-8') as f:
                    yaml.dump(default_eula_data, f, allow_unicode=True)
                logger.info(f"已创建用户EULA状态文件: {self.user_eula_file}")
            else:
                logger.info(f"用户EULA状态文件已存在: {self.user_eula_file}")
                
        except Exception as e:
            logger.error(f"创建数据文件失败: {e}")

    async def load_config_files(self):
        """加载配置文件"""
        try:
            # 加载信息链接配置
            if os.path.exists(self.info_links_file):
                with open(self.info_links_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    self.info_links = data.get('info_links', {})
            else:
                logger.warning(f"信息链接配置文件不存在: {self.info_links_file}")
            
            # 加载用户EULA状态
            if os.path.exists(self.user_eula_file):
                with open(self.user_eula_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    self.user_eula_status = data.get('users', {})
            else:
                logger.warning(f"用户EULA状态文件不存在: {self.user_eula_file}")
                
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")

    async def save_user_eula_status(self):
        """保存用户EULA状态"""
        try:
            with open(self.user_eula_file, 'w', encoding='utf-8') as f:
                yaml.dump({'users': self.user_eula_status}, f, allow_unicode=True)
        except Exception as e:
            logger.error(f"保存用户EULA状态失败: {e}")

    def check_eula_status(self, user_id: str, group_id: str = None) -> bool:
        """检查EULA状态"""
        if group_id:
            # 群聊模式：检查群聊是否已有人接受EULA
            group_key = f"group_{group_id}"
            return self.user_eula_status.get(group_key, False)
        else:
            # 私聊模式：检查用户是否已接受EULA
            return self.user_eula_status.get(user_id, False)

    def is_new_target(self, user_id: str, group_id: str = None) -> bool:
        """检查是否为新用户/新群聊"""
        if group_id:
            # 群聊模式：检查群聊是否为新群聊
            group_key = f"group_{group_id}"
            return group_key not in self.user_eula_status
        else:
            # 私聊模式：检查是否为新用户
            return user_id not in self.user_eula_status

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        """在发送消息前检查EULA状态并装饰结果"""
        user_id = str(event.get_sender_id())
        group_id = event.get_group_id()
        group_id_str = str(group_id) if group_id else None
        
        # 如果是EULA命令，直接跳过检查
        if event.message_str.startswith('/eula'):
            return
        
        # 检查EULA状态
        if self.is_new_target(user_id, group_id_str) or not self.check_eula_status(user_id, group_id_str):
            # 清空原有的消息链，替换为EULA提醒
            result = event.get_result()
            result.chain.clear()
            
            if group_id_str:
                # 群聊模式
                eula_message = """
欢迎使用本机器人！
本群需要至少一位成员接受用户协议(EULA)才能使用机器人功能。
🔗：https://gameswu.github.io/nya_doc/#/EULA
✅ 接受协议：发送 `/eula true`
❌ 拒绝协议：发送 `/eula false`
注意：群内任意成员接受协议后，整个群聊都可以正常使用机器人功能。
                """.strip()
                
                # 标记群聊为未接受状态（如果是新群聊）
                if self.is_new_target(user_id, group_id_str):
                    group_key = f"group_{group_id_str}"
                    self.user_eula_status[group_key] = False
                    await self.save_user_eula_status()
            else:
                # 私聊模式
                eula_message = """
欢迎使用本机器人！
您需要先接受用户协议(EULA)才能使用机器人功能。
🔗：https://gameswu.github.io/nya_doc/#/EULA
✅ 接受协议：发送 `/eula true`
❌ 拒绝协议：发送 `/eula false`
注意：只有接受协议后才能正常使用机器人功能。
                """.strip()
                
                # 标记用户为未接受状态（如果是新用户）
                if self.is_new_target(user_id, group_id_str):
                    self.user_eula_status[user_id] = False
                    await self.save_user_eula_status()
            
            # 添加EULA提醒到消息链
            from astrbot.api.message_components import Plain
            result.chain.append(Plain(eula_message))

    @filter.command("eula")
    async def handle_eula(self, event: AstrMessageEvent, arg: str):
        """处理EULA接受/拒绝命令"""
        user_id = str(event.get_sender_id())
        user_name = event.get_sender_name()
        group_id = event.get_group_id()
        group_id_str = str(group_id) if group_id else None
        
        # 解析命令参数
        choice = arg.lower()

        if choice == "true":
            if group_id_str:
                # 群聊模式：群聊接受EULA
                group_key = f"group_{group_id_str}"
                self.user_eula_status[group_key] = True
                await self.save_user_eula_status()
                yield event.plain_result(f"✅ {user_name} 已为本群接受用户协议！现在群内所有成员都可以正常使用机器人功能了。tips: 您可以使用`/info`命令来获取更多信息页面链接。")
                logger.info(f"用户 {user_name}({user_id}) 为群聊 {group_id_str} 接受了EULA")
            else:
                # 私聊模式：个人接受EULA
                self.user_eula_status[user_id] = True
                await self.save_user_eula_status()
                yield event.plain_result(f"✅ {user_name}，您已成功接受用户协议！现在可以正常使用机器人功能了。tips: 您可以使用`/info`命令来获取更多信息页面链接。")
                logger.info(f"用户 {user_name}({user_id}) 接受了EULA")
            
        elif choice == "false":
            if group_id_str:
                # 群聊模式：拒绝群聊EULA
                group_key = f"group_{group_id_str}"
                self.user_eula_status[group_key] = False
                await self.save_user_eula_status()
                yield event.plain_result(f"❌ {user_name} 已拒绝为本群接受用户协议。在有成员接受协议之前，群内无法使用机器人功能。")
                logger.info(f"用户 {user_name}({user_id}) 为群聊 {group_id_str} 拒绝了EULA")
            else:
                # 私聊模式：个人拒绝EULA
                self.user_eula_status[user_id] = False
                await self.save_user_eula_status()
                yield event.plain_result(f"❌ {user_name}，您已拒绝用户协议。在接受协议之前，您无法使用机器人功能。")
                logger.info(f"用户 {user_name}({user_id}) 拒绝了EULA")
            
        else:
            yield event.plain_result("❌ 参数错误！请使用 true（接受）或 false（拒绝）")

    @filter.command("info")
    async def handle_info(self, event: AstrMessageEvent, keyword: str = None):
        """处理信息查询命令"""
        # EULA检查已经在on_decorating_result中统一处理，这里直接处理业务逻辑
        
        if not keyword:
            # 显示可用的关键词列表
            available_keywords = list(self.info_links.keys())
            if available_keywords:
                keywords_text = "、".join(available_keywords)
                yield event.plain_result(f"📚 可用的信息关键词：\n{keywords_text}\n\n使用方法：/info [关键词]")
            else:
                yield event.plain_result("❌ 暂无可用的信息链接配置")
            return
        
        # 查找对应的链接
        if keyword in self.info_links:
            link = self.info_links[keyword]
            yield event.plain_result(f"📖 {keyword} 信息页面：\n{link}")
            logger.info(f"用户查询了信息关键词: {keyword}")
        else:
            available_keywords = list(self.info_links.keys())
            keywords_text = "、".join(available_keywords)
            yield event.plain_result(f"❌ 未找到关键词 '{keyword}' 对应的信息页面。\n\n可用关键词：{keywords_text}")

    async def terminate(self):
        """插件销毁方法"""
        logger.info("InfoDoc插件已卸载")
