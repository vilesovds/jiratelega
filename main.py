import json
from configmanager import config
from jiramanager import create_task
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning
import logging
from usermanager import UserManager
from io import BytesIO
from demoji import replace

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

user_manager = UserManager(config['db']['url'], config['db']['users_table'])

AUTH, MENU, SUB_MENU, DESCRIPTION, TYPING, FILES, STOPPING, \
    SUBLEVELS, START_OVER, = map(chr, range(9))
# Shortcut for ConversationHandler.END
END = ConversationHandler.END

with open('menu.json', 'r', encoding='utf-8') as handle:
    menu = json.load(handle)


async def begin_of_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data

    buttons = [
        [InlineKeyboardButton(text=level['label'], callback_data=f'{SUB_MENU}{chr(i)}')] for i, level in
        enumerate(menu)
    ]

    buttons.append(
        [
            InlineKeyboardButton(text="🔚Закончить", callback_data=f'{END}'),
        ]
    )

    keyboard = InlineKeyboardMarkup(buttons)

    # If we're starting over we don't need to send a new message
    if context.user_data.get(START_OVER):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text='Выберите тему обращения', reply_markup=keyboard)
    else:
        user_data['user'] = update.message.from_user.id
        text = f"Приветствую, {user_manager.get_user_name(update.message.from_user.id)} выберите тему обращения"
        await update.message.reply_text(text=text, reply_markup=keyboard)

    context.user_data[START_OVER] = False
    return MENU


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f'is user {user.username} authorized? {user_manager.is_authorized_user(user.id)}')

    if user_manager.is_authorized_user(user.id):
        return await begin_of_conversation(update, context)

    contact_keyboard = KeyboardButton(text="☎ send contact", request_contact=True)
    custom_keyboard = [[contact_keyboard]]
    reply_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        text="Авторизация по номеру телефона ☎",
        reply_markup=reply_markup)
    return AUTH


async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("Id of %s: %s. tel: %s", user.username, user.id, update.message.contact.phone_number)
    phone_number = update.message.contact.phone_number.replace('+', '')

    if user_manager.authorize_user(phone_number, user.id, user.username):
        logger.info('authorized user')
        user_manager.authorize_user(phone_number, user.id, user.username)

        return await begin_of_conversation(update, context)
    else:
        await update.message.reply_text(
            'Пользователя с таким номером нет в списке',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "До скорых встреч",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End conversation from InlineKeyboardButton."""
    await update.callback_query.answer()

    text = "Всего хорошего!"
    await update.callback_query.edit_message_text(text=text)

    return END


async def ask_for_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user_data = context.user_data
    logger.debug(
        f'ord[1]: {ord(update.callback_query.data[1])} '
    )
    sub_index = ord(update.callback_query.data[1])
    user_data['sub_index'] = sub_index
    text = "Введите описание задачи"
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text=text)

    return TYPING


async def save_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user_data = context.user_data
    user_data['input'] = update.message.text
    logger.debug(f'user input: {update.message.text}')

    buttons = [
        [
            InlineKeyboardButton(text="Отмена", callback_data=str(END)),
            InlineKeyboardButton(text="Далее", callback_data=str(FILES)),
        ],
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    text = "Отправьте файлы или нажмите далее"
    await update.message.reply_text(text=text, reply_markup=keyboard)
    return FILES


async def save_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user_data = context.user_data
    user_data[START_OVER] = False

    attachment = update.message.effective_attachment
    if isinstance(attachment, tuple):
        attachment = attachment[-1]
    logger.debug(attachment)

    file_id = await attachment.get_file()
    logger.debug(file_id)
    # hack for images
    file_name = attachment.file_name if hasattr(attachment, 'file_name') \
        else f'{attachment.file_unique_id}.{file_id.file_path.split(".")[-1]}'
    logger.info(file_name)

    out = BytesIO()
    await file_id.download_to_memory(out)
    doc = {'filename': file_name, 'data': out}
    current_files = user_data.get('files', [])
    current_files.append(doc)
    user_data['files'] = current_files

    buttons = [
        [
            InlineKeyboardButton(text="Отмена", callback_data=str(END)),
            InlineKeyboardButton(text="Завершить", callback_data=str(FILES)),
        ],
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(text='Файл получен', reply_markup=ReplyKeyboardRemove())

    text = "Отправьте ещё файлы или нажмите Завершить"
    await update.message.reply_text(text=text, reply_markup=keyboard)
    return FILES


async def construct_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user_data = context.user_data
    user_data[START_OVER] = False
    logger.debug(f'index: {user_data.get("index")} '
                 f'sub_index: {user_data.get("sub_index")} '
                 f'input : {user_data.get("input")}')

    user_id = user_data['user']
    menu_index = user_data.get("index")
    sub_menu_index = user_data.get("sub_index")

    files = user_data.get('files', [])

    sub_menu = menu[menu_index]["submenu"][sub_menu_index]["label"]
    description = f'*Сотрудник*: {user_manager.get_user(user_id)}\n' \
                  f'*Тема*: {menu[menu_index]["label"]}-{sub_menu}\n' \
                  f'*Сообщение*: {user_data.get("input")}'

    # clean emoji
    request_type = replace(sub_menu)
    email = user_manager.get_user_email(user_id)
    task = create_task(
        description=description,
        request_type=request_type,
        assignee=menu[menu_index]['submenu'][sub_menu_index].get('assignee'),
        files=files,
        reporter=email
    )
    if task:
        text = f'Заявка {task} принята.\nЕсли хотите открыть новую задачу, то воспользуйтесь командой /start'
    else:
        text = f'Произошла ошибка при попытке создания заявки. Попробуйте начать заного, для этого ' \
               f'воспользуйтесь командой /start'

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text=text)

    return STOPPING


async def select_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    await update.callback_query.answer()
    user_data = context.user_data

    index = ord(update.callback_query.data[1])
    user_data['index'] = index
    buttons = [[InlineKeyboardButton(text=level['label'], callback_data=f'{SUBLEVELS}{chr(i)}')] for i, level in
               enumerate(menu[index]['submenu'])]

    buttons.append(
        [
            InlineKeyboardButton(text="🔙Назад", callback_data=str(END)),
        ]
    )
    keyboard = InlineKeyboardMarkup(buttons)
    text = "Выберите подуровень"
    await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)

    return DESCRIPTION


async def end_describing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.debug(f'end_describing')
    context.user_data[START_OVER] = True
    await begin_of_conversation(update, context)

    return END


async def end_second_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to top level conversation."""
    context.user_data[START_OVER] = True
    await begin_of_conversation(update, context)

    return END


async def stop_nested(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Completely end conversation from within nested conversation."""
    await update.message.reply_text("До свидания")

    return STOPPING


def main() -> None:
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(config['telegram_bot_token']).build()
    description_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_for_input, pattern=f'^{SUBLEVELS}.$')
        ],
        states={
            TYPING: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_input)],
            FILES: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, save_files),
                CallbackQueryHandler(construct_task, pattern=f'{FILES}$'),
            ]

        },
        fallbacks=[
            CallbackQueryHandler(end_describing, pattern=f'^{END}$'),
            CommandHandler("stop", stop_nested),
        ],
        map_to_parent={
            # Return to second level menu
            END: END,
            # End conversation altogether
            STOPPING: STOPPING,
        },
    )

    # Set up second level ConversationHandler
    sub_level_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(select_level, pattern=f'^{SUB_MENU}.$')],
        states={
            DESCRIPTION: [description_conv],
        },
        fallbacks=[
            CallbackQueryHandler(end_second_level, pattern=f'^{END}$'),
            CommandHandler("stop", stop_nested),
        ],
        map_to_parent={
            # Return to top level menu
            END: MENU,
            # End conversation altogether
            STOPPING: END,
        },
    )

    selection_handlers = [
        sub_level_conv,
        CallbackQueryHandler(end, pattern=f"^{END}$"),
    ]
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AUTH: [MessageHandler(filters.CONTACT, auth)],
            MENU: selection_handlers,
            STOPPING: [CommandHandler("start", start)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
