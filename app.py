import streamlit as st
import pandas as pd
import io

# Настройка страницы
st.set_page_config(page_title="Объединённый анализ сетей", layout="centered")
st.title("📊 Обработка нескольких файлов (ГРИН, Санта и др.)")
st.markdown("Загрузите файлы от разных сетей — получите один сводный отчёт.")

def process_file(uploaded_file):
    # Читаем файл
    try:
        df = pd.read_excel(uploaded_file, header=None)
    except Exception as e:
        st.error(f"Ошибка чтения файла {uploaded_file.name}: {e}")
        return None

    # Ищем строку с "Сеть"
    header_row_idx = df[df[0] == "Сеть"].index
    if len(header_row_idx) == 0:
        st.warning(f"❌ Не найдена строка с 'Сеть' в файле: {uploaded_file.name}")
        return None
    header_row_idx = header_row_idx[0]

    # Устанавливаем заголовки
    df.columns = df.iloc[header_row_idx]
    df = df[header_row_idx + 1:].reset_index(drop=True)

    # Очищаем названия столбцов
    df.columns = [str(col).strip() for col in df.columns]

    # Проверяем обязательные столбцы
    required_cols = ["Адрес торгового объекта", "Описание номенклатуры", "Штрих_код", "Остаток"]
    for col in required_cols:
        if col not in df.columns:
            st.error(f"❌ В файле {uploaded_file.name} не найден столбец: {col}")
            return None

    # Извлекаем название сети из первой строки данных
    network = df["Сеть"].dropna().iloc[0] if "Сеть" in df.columns else "Неизвестно"

    # Функция для СКЮ КОД
    def get_sku(barcode):
        try:
            barcode_str = str(int(barcode))
            if len(barcode_str) >= 5:
                last_5 = barcode_str[-5:]
                return last_5[:4].zfill(4)
            else:
                return "0000"
        except:
            return "0000"

    # Функция для Категории
    def get_category(name):
        if pd.isna(name) or not isinstance(name, str):
            return "Прочие"
        name = str(name)
        if "ГринФилд" in name:
            return "Greenfield"
        elif "Тесс" in name:
            return "Tess"
        elif "Жокей" in name:
            return "Жокей раствор" if "раств." in name else "Жокей Натуральный"
        elif "Жардин" in name:
            return "JARDIN раствор" if "раств." in name else "JARDIN натур"
        elif any(x in name for x in ["Нури", "Ява", "Канди", "Гита"]):
            return "Принцессы"
        else:
            return "Прочие"

    # Применяем
    df["Категория"] = df["Описание номенклатуры"].apply(get_category)
    df["СКЮ КОД"] = df["Штрих_код"].apply(get_sku)

    # Очистка и преобразование Остаток
    def safe_to_numeric(val):
        if pd.isna(val):
            return 0
        if isinstance(val, str):
            val_clean = val.replace(",", ".").strip()
            try:
                return float(val_clean)
            except:
                return 0
        return float(val)

    df["Остаток"] = df["Остаток"].apply(safe_to_numeric)

    # Фильтр: только где Остаток > 0
    df_filtered = df[df["Остаток"] > 0].copy()

    if df_filtered.empty:
        return None

    # Добавляем имя сети
    df_filtered["Сеть"] = network

    # Группировка: Адрес + Категория → список СКЮ КОДОВ
    pivot = df_filtered.groupby(
        ["Сеть", "Адрес торгового объекта", "Категория"], as_index=False
    )["СКЮ КОД"].apply(lambda x: ", ".join(x)).rename(columns={"СКЮ КОД": "СКЮ КОДЫ"})

    return pivot

# === Интерфейс ===
uploaded_files = st.file_uploader(
    "Загрузите файлы от разных сетей",
    type=["xls", "xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Обработка файлов..."):
        all_data = []

        for file in uploaded_files:
            st.info(f"Обработка: {file.name}")
            result = process_file(file)
            if result is not None:
                all_data.append(result)

        if not all_data:
            st.warning("❌ Ни в одном файле не найдены позиции с остатком > 0.")
        else:
            # Объединяем все данные
            final_df = pd.concat(all_data, ignore_index=True)

            # Сортируем: сначала по Сети, потом по Адресу
            final_df = final_df.sort_values(by=["Сеть", "Адрес торгового объекта"]).reset_index(drop=True)

            st.success("✅ Все файлы обработаны!")
            st.dataframe(final_df, use_container_width=True)

            # Подготовка файла для скачивания
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                final_df.to_excel(writer, index=False, sheet_name="Сводная по сетям")
            output.seek(0)

            st.download_button(
                label="📥 Скачать общий сводный файл (Excel)",
                data=output,
                file_name="Сводная_по_всем_сетям.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("Пожалуйста, загрузите один или несколько файлов.")
